"""政策检索：dknowc 可信搜索客户端 + 过滤排序 + 演示模式。

材料结构（内部统一）：
{n, title, source, url, region, date, reliability, doc_no, segments:[{title,content}]}
"""
import re
from urllib.parse import urlparse

import httpx

from . import config, db
from .geo_data import GEO_DETECT_CITIES

RELIABILITY_ORDER = {"高": 3, "较高": 2, "一般": 1}

# 标题/来源里要求"地市名 + 行政后缀"才判为其他地市，避免"沟通化解/今天水费/开封信"等常用词误伤
_OTHER_CITY_RE = re.compile(
    "(" + "|".join(sorted(GEO_DETECT_CITIES, key=len, reverse=True)) + r")(?:市|区|县|州|地区|盟)"
)


def _geo_ok(item: dict, city_core: str) -> bool:
    """地域是否与办理地市一致：材料属其他地市（且未同时提到本地）则不通过；
    本地、下辖县市、省级、国家级、无地市标识的材料通过。"""
    if not city_core:
        return True
    region = str(item.get("region") or "")
    title_src = str(item.get("title") or "") + " " + str(item.get("source") or "")
    if city_core in region or city_core in title_src:
        return True
    # region 为结构化地域字段，出现其他地市名即剔除
    for c in GEO_DETECT_CITIES:
        if c != city_core and c in region:
            return False
    # 标题/来源需"地市名+行政后缀"才算命中（防常用词误伤）
    for m in _OTHER_CITY_RE.finditer(title_src):
        if m.group(1) != city_core:
            return False
    return True


class RetrievalError(Exception):
    def __init__(self, message: str, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


def _domain(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except Exception:
        return ""


def _is_authoritative(item: dict, auth_domains: list[str], auth_names: list[str]) -> bool:
    dom = _domain(item.get("url", ""))
    if dom and any(dom == d or dom.endswith("." + d) for d in auth_domains):
        return True
    src = (item.get("source") or "") + (item.get("title") or "")
    return any(name in src for name in auth_names)


def _blocked(item: dict, blocked_keywords: list[str]) -> bool:
    hay = " ".join(str(item.get(k, "")) for k in ("source", "title", "url"))
    return any(kw and kw in hay for kw in blocked_keywords)


def filter_rank(articles: list[dict], settings: dict) -> tuple[list[dict], list[dict]]:
    """按《整体设计》4.2 规则过滤排序，返回 (保留Top-N, 被剔除清单)。"""
    auth_domains = db.setting_lines(settings, "authoritative_domains")
    auth_names = db.setting_lines(settings, "authoritative_source_names")
    blocked_keywords = db.setting_lines(settings, "blocked_source_keywords")
    top_n = db.setting_int(settings, "top_n", 3)
    city_core = (settings.get("default_service_area") or "").replace("市", "").strip()

    kept, dropped = [], []
    for a in articles:
        a["authoritative"] = _is_authoritative(a, auth_domains, auth_names)
        rel = RELIABILITY_ORDER.get(a.get("reliability") or "", 1)
        if _blocked(a, blocked_keywords):
            a["drop_reason"] = "命中屏蔽源关键词"
            dropped.append(a)
            continue
        if not _geo_ok(a, city_core):
            a["drop_reason"] = "非本地办理地域（其他地市）"
            dropped.append(a)
            continue
        if rel <= 1 and not a["authoritative"]:
            a["drop_reason"] = "可信度一般且非权威源"
            dropped.append(a)
            continue
        if not a.get("segments"):
            a["drop_reason"] = "无可用段落"
            dropped.append(a)
            continue
        kept.append(a)

    # 权威源/法规优先，其余保留 dknowc 自身的相关性排序（不用日期打乱）
    kept.sort(key=lambda a: (not (a["authoritative"] or bool(a.get("doc_no"))), a.get("_idx", 999)))
    kept = kept[:top_n]
    for i, a in enumerate(kept, 1):
        a["n"] = i
    return kept, dropped


def _parse_dknowc(payload: dict, segment_count: int) -> tuple[list[dict], list[dict]]:
    container = payload
    for key in ("content", "data"):
        if isinstance(container, dict) and isinstance(container.get(key), dict):
            container = container[key]
    if not isinstance(container, dict):
        container = {}

    policy_files = []
    for pf in container.get("policyFiles") or []:
        policy_files.append({
            "title": pf.get("title") or "",
            "url": pf.get("sourceUrl") or "",
            "date": pf.get("createDate") or "",
            "reliability": pf.get("createDateReliability") or "",
            "doc_no": pf.get("writtenText") or "",
        })

    raw_articles = container.get("检索文章") or container.get("articles") or []
    if not isinstance(raw_articles, list):
        raw_articles = []
    articles = []
    for _idx, art in enumerate(raw_articles):
        if not isinstance(art, dict):
            continue
        segs = []
        for s in (art.get("段落") or [])[: max(segment_count, 1)]:
            if not isinstance(s, dict):
                continue
            content = re.sub(r"\s+", " ", (s.get("内容") or "")).strip()  # 折叠 dknowc 抓取残留的制表符/空白
            if content:
                segs.append({"title": (s.get("标题") or "").strip(), "content": content})
        title = (art.get("文章标题") or art.get("title") or "").strip()
        doc_no = ""
        for pf in policy_files:  # 标题相符的规范性文件带出文号
            if pf["doc_no"] and pf["title"] and (pf["title"] in title or title in pf["title"]):
                doc_no = pf["doc_no"]
                break
        articles.append({
            "title": title,
            "source": (art.get("数据源") or "").strip(),
            "url": (art.get("源网址") or "").strip(),
            "region": (art.get("办理地域") or "").strip(),
            "date": (art.get("发布日期") or "").strip(),
            "reliability": (art.get("发布日期可信度") or "").strip(),
            "doc_no": doc_no,
            "segments": segs,
            "_idx": _idx,
        })
    return articles, policy_files


def search_live(query: str, service_area: str, eff_time: str, settings: dict) -> dict:
    body = {
        "query": query,
        "policy": True,
        "simplified": True,
        "segmentCount": db.setting_int(settings, "segment_count", 3),
    }
    if service_area:
        body["service_area"] = [service_area]
    if eff_time:
        body["eff_time"] = [eff_time]
    try:
        resp = httpx.post(
            config.DKNOWC_ENDPOINT,
            json=body,
            headers={"api-key": config.DKNOWC_API_KEY, "Content-Type": "application/json; charset=utf-8"},
            timeout=config.RETRIEVAL_TIMEOUT,
        )
    except httpx.TimeoutException:
        raise RetrievalError("政策检索超时，请稍后重试", retryable=True)
    except httpx.HTTPError as e:
        raise RetrievalError(f"政策检索网络异常：{e.__class__.__name__}", retryable=True)

    if resp.status_code == 401 or resp.status_code == 403:
        raise RetrievalError("政策检索接口鉴权失败（请检查 DKNOWC_API_KEY 配置）", retryable=False)
    if resp.status_code == 402:
        raise RetrievalError("政策检索接口余额不足，请充值或更换 DKNOWC_API_KEY", retryable=False)
    if resp.status_code == 429:
        raise RetrievalError("政策检索接口限流，请稍后重试", retryable=True)
    if resp.status_code >= 400:
        raise RetrievalError(f"政策检索服务异常（HTTP {resp.status_code}），请稍后重试", retryable=True)
    try:
        payload = resp.json()
    except Exception:
        raise RetrievalError("政策检索返回格式异常", retryable=True)

    seg_cnt = db.setting_int(settings, "segment_count", 3)
    articles, policy_files = _parse_dknowc(payload, seg_cnt)
    kept, dropped = filter_rank(articles, settings)
    return {"mode": "live", "materials": kept, "policy_files": policy_files,
            "raw_count": len(articles), "dropped": [{"title": d.get("title"), "reason": d.get("drop_reason")} for d in dropped]}


# ---------------- 演示模式 ----------------
# 说明：无 DKNOWC_API_KEY 时启用，返回按主题匹配的演示材料，UI 全程带「演示数据」标识。
# 演示材料内容为常见政策方向的概括性示意，不代表现行有效条文。

_FIXTURES = [
    (("公积金", "提取", "租房"), [
        dict(title="枣庄市住房公积金管理办法（演示材料）", source="枣庄市住房公积金管理中心", url="",
             region="枣庄", date="2023-06-01", reliability="高", doc_no="枣公积金〔2023〕12号",
             segments=[{"title": "第十一条 提取条件", "content": "职工本人及配偶在本市城镇规划区内无自住住房且租赁自住住房，已按时连续足额缴存住房公积金满3个月的，可按租房提取方式提取本人住房公积金。名下有自住住房的，不符合租房提取条件。职工购买、建造、翻建、大修自住住房，或偿还购房贷款本息的，可按相应情形申请提取。"}]),
    ]),
    (("供暖", "暖气", "供热", "采暖"), [
        dict(title="山东省供热条例（演示材料）", source="山东省人民代表大会常务委员会", url="",
             region="山东省", date="2024-01-01", reliability="高", doc_no="",
             segments=[{"title": "计费与采暖期", "content": "供热价格按照价格主管部门核定标准执行，实行按套内建筑面积计收热费的，收费面积以不动产权属证书记载或具有资质的测绘机构出具的测绘报告为准。用户对收费面积有异议的，可持相关证明材料向供热企业申请核定。供热企业应当在规定采暖期内持续稳定供热，因检修等原因影响供热的，应当提前公告并及时恢复。"}]),
        dict(title="枣庄市城市集中供热管理办法（演示材料）", source="枣庄市人民政府", url="",
             region="枣庄", date="2022-11-01", reliability="较高", doc_no="枣政发〔2022〕18号",
             segments=[{"title": "温度标准与退费", "content": "在正常天气条件下，用户卧室、起居室温度不应低于规定标准。因供热企业原因导致室温不达标的，用户可要求测温并按规定减收或退还相应热费。供热设施保修期内出现质量问题的，由建设单位负责维修。"}]),
    ]),
    (("工资", "欠薪", "拖欠", "农民工"), [
        dict(title="保障农民工工资支付条例（演示材料）", source="国务院", url="",
             region="全国", date="2020-05-01", reliability="高", doc_no="国令第724号",
             segments=[{"title": "总包责任与清偿", "content": "建设单位应当按合同约定及时拨付工程款。分包单位拖欠农民工工资的，由施工总承包单位先行清偿，再依法进行追偿。农民工可向人力资源社会保障行政部门投诉，或通过全国根治欠薪线索反映平台反映欠薪线索。"}]),
        dict(title="劳动保障监察条例（演示材料）", source="国务院", url="",
             region="全国", date="2004-12-01", reliability="高", doc_no="国令第423号",
             segments=[{"title": "投诉处理", "content": "劳动者对用人单位拖欠工资等违反劳动保障法律行为，有权向劳动保障行政部门投诉。劳动保障行政部门应当依法受理并调查处理。"}]),
    ]),
    (("物业", "梯控", "电梯", "停水", "停电"), [
        dict(title="中华人民共和国民法典（物业服务合同相关，演示材料）", source="全国人民代表大会", url="",
             region="全国", date="2021-01-01", reliability="高", doc_no="",
             segments=[{"title": "第九百四十四条", "content": "业主应当按照约定向物业服务人支付物业费。业主违反约定逾期不支付物业费的，物业服务人可以催告其在合理期限内支付；合理期限届满仍不支付的，物业服务人可以提起诉讼或者申请仲裁。物业服务人不得采取停止供电、供水、供热、供燃气等方式催交物业费。"},
                       {"title": "第二百七十一条、第二百七十八条", "content": "业主对建筑物内的住宅、经营性用房等专有部分享有所有权，对专有部分以外的共有部分享有共有和共同管理的权利。改建、重建建筑物及其附属设施等重大事项，应当由业主共同决定。"}]),
    ]),
    (("入学", "学位", "随迁", "转学"), [
        dict(title="关于做好城区外来务工人员随迁子女入学工作的通知（演示材料）", source="枣庄市教育局", url="",
             region="枣庄", date="2024-05-20", reliability="高", doc_no="枣教发〔2024〕17号",
             segments=[{"title": "入学材料与定点学校", "content": "随迁子女入学须提供：父母及学生身份证信息；父母一方居住证（半年以上）；房产证、不动产证、购房网签合同或房屋租赁登记备案证明（半年以上）；父母一方经备案的劳动合同及社会保险证明，或营业执照（半年以上）。符合条件的随迁子女依据居住证地址，由教育部门安排至定点学校就读。"}]),
    ]),
    (("医保", "报销", "备案", "异地就医"), [
        dict(title="异地就医备案服务规范（演示材料）", source="枣庄市医疗保障局", url="",
             region="枣庄", date="2023-09-01", reliability="高", doc_no="",
             segments=[{"title": "备案材料", "content": "异地长期居住人员办理备案，须提供就医地居住证或居民户口簿（户口簿首页和本人常住人口登记卡）等长期居住证明材料。备案可通过线上服务渠道提交，材料不全的将退回补正。临时外出就医人员按相应规定办理。"}]),
    ]),
]

_GENERIC = [
    dict(title="12345政务服务便民热线工单办理规范（演示材料）", source="枣庄市人民政府办公室", url="",
         region="枣庄", date="2023-03-01", reliability="较高", doc_no="",
         segments=[{"title": "办理与答复", "content": "承办单位应当在规定时限内核实办理群众诉求，依法依规答复；对不属于受理范围或诉求缺乏政策依据的，应当耐心解释说明并告知可行的救济途径。答复应当事实清楚、依据明确、用语规范。"}]),
]


def search_mock(query: str, settings: dict) -> dict:
    matched = None
    for keywords, fixtures in _FIXTURES:
        if any(k in query for k in keywords):
            matched = [dict(f) for f in fixtures]
            break
    if matched is None:
        matched = [dict(f) for f in _GENERIC]
    kept, dropped = filter_rank(matched, settings)
    policy_files = [{"title": m["title"], "url": m.get("url", ""), "date": m.get("date", ""),
                     "reliability": m.get("reliability", ""), "doc_no": m.get("doc_no", "")}
                    for m in kept if m.get("doc_no")]
    return {"mode": "mock", "materials": kept, "policy_files": policy_files,
            "raw_count": len(matched), "dropped": []}


def _merge_private(base: dict, query: str, settings: dict) -> dict:
    """把私有政策库命中的材料并入结果，本地政策优先展示。"""
    from . import private_db
    if not (db.setting_bool(settings, "private_db_enabled") and private_db.available()):
        return base
    top_n = db.setting_int(settings, "top_n", 4)
    seg_cnt = db.setting_int(settings, "segment_count", 3)
    try:
        pmats = private_db.search(query, top_k=top_n, segment_count=seg_cnt)
    except Exception:
        pmats = []
    if not pmats:
        return base
    # 本地政策优先，但保留至少一个 dknowc 名额以便对照
    reserve = 1 if base["materials"] else 0
    pmats = pmats[: max(1, top_n - reserve)]
    merged = pmats + base["materials"]
    merged = merged[:top_n]
    for i, m in enumerate(merged, 1):
        m["n"] = i
    base["materials"] = merged
    base["has_private"] = any(m.get("private") for m in merged)
    return base


def search(query: str, service_area: str, eff_time: str, settings: dict) -> dict:
    if config.RETRIEVAL_MOCK:
        base = search_mock(query, settings)
    else:
        base = search_live(query, service_area, eff_time, settings)
    return _merge_private(base, query, settings)
