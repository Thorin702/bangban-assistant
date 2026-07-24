"""办件研判（基于历史工单结果标签）：时限研判 + 满意度处方 + 关联预警。
只做承办人下笔前的背景判断，不做责任研判（一线自己是第一责任人）。"""
import re
import statistics

from . import cases, generation

_SUFFIX = r"(小区|花园|家园|新村|社区|嘉园|华府|公馆|广场|苑|府邸|名邸|庄园|山庄|别苑)"
_COMMUNITY_RE = re.compile(r"([一-龥A-Za-z0-9]{2,12}?)" + _SUFFIX)
# 诉求前导词，避免把"反映/来电人反映/位于"等吞进小区名（re.search 从最左匹配）
_COMM_STOP = ["来电人反映", "来电人", "反映", "投诉举报", "投诉", "举报", "咨询", "位于", "关于",
              "本人", "市民", "群众", "居民", "业主", "家住", "我家", "我们", "现在", "现", "我", "在", "有", "称", "说"]


def _strip_lead(core: str) -> str:
    changed = True
    while changed and len(core) > 2:
        changed = False
        for s in _COMM_STOP:
            if core.startswith(s) and len(core) - len(s) >= 2:
                core = core[len(s):]
                changed = True
                break
    return core


def _community(query: str):
    """返回 (显示名, 搜索核心名)。核心名去前导停用词，用于正文匹配（正文常不带后缀）。"""
    m = _COMMUNITY_RE.search(query or "")
    if not m:
        return "", ""
    core = _strip_lead(m.group(1))
    suffix = m.group(2)
    display = core + suffix
    return display, (core if len(core) >= 3 else display)


def _dominant_c2(rows: list[dict]) -> str:
    from collections import Counter
    c = Counter(r["c2"] for r in rows if r.get("c2"))
    return c.most_common(1)[0][0] if c else ""


def compute_signals(query: str) -> dict | None:
    """秒级计算三个信号（不含满意度处方全文，处方按需再生成）。"""
    rows = cases.research_rows(query, limit=60)
    if len(rows) < 5:  # 样本太少不研判，避免误导
        return None

    signal = {"sample_n": len(rows), "deadline": None, "satisfaction": None, "related": None}

    # 时限研判
    days = [r["days"] for r in rows if r["days"] is not None]
    overdue = [r for r in rows if r["is_overdue"] == "是"]
    if len(days) >= 5:
        med = int(statistics.median(days))
        rate = round(len(overdue) / len(rows), 3)
        level = "high" if rate >= 0.15 else ("mid" if rate >= 0.05 else "low")
        signal["deadline"] = {"median_days": med, "overdue_rate": rate, "n": len(days), "level": level}

    # 满意度（率；处方全文按需生成）
    rated = [r for r in rows if r["is_satisfied"] in ("满意", "基本满意", "不满意")]
    sat = [r for r in rated if r["is_satisfied"] in ("满意", "基本满意")]
    if len(rated) >= 5:
        rate = round(len(sat) / len(rated), 3)
        level = "low" if rate < 0.6 else ("mid" if rate < 0.8 else "high")
        signal["satisfaction"] = {"rate": rate, "n": len(rated), "unsat_n": len(rated) - len(sat), "level": level}

    # 关联预警（同小区历史同类件数）
    comm_display, comm_key = _community(query)
    if comm_key:
        c2 = _dominant_c2(rows)
        rel = cases.related_by_community(comm_key, c2, limit=6)
        if rel["count"] >= 2:
            level = "high" if rel["count"] >= 5 else "mid"
            signal["related"] = {"community": comm_display, "category": c2, "count": rel["count"],
                                 "cases": rel["cases"], "level": level}
    return signal


PRESCRIPTION_SYSTEM = """你是基层帮办智能助手的"满意度处方"模块。给定同类历史工单中【满意】与【不满意】两组真实办理情况，请对比提炼出让本类诉求办到满意的关键做法。规则：
1) 只依据给定案例，不得编造；
2) 输出两部分，各以标记单独起一行开头：【办到满意的关键】【易导致不满意】；
3) 每部分 2-4 条，每条一句、具体可执行（如"现场核实并向诉求人反馈测量数据"，而非"高度重视"）；
4) 是经验参考不是承诺，不涉及具体政策口径；总字数不超过260字。"""


def build_prescription_prompt(query: str) -> str | None:
    rows = cases.research_rows(query, limit=60)
    sat = [r for r in rows if r["is_satisfied"] in ("满意", "基本满意") and r.get("handling")][:6]
    unsat = [r for r in rows if r["is_satisfied"] == "不满意" and r.get("handling")][:6]
    if len(sat) < 2:
        return None
    lines = [f"【当前诉求】{query}", "", "【满意案例的办理情况】"]
    for i, r in enumerate(sat, 1):
        lines.append(f"{i}. {r['handling'][:220]}")
    if unsat:
        lines += ["", "【不满意案例的办理情况】"]
        for i, r in enumerate(unsat, 1):
            lines.append(f"{i}. {r['handling'][:220]}")
    return "\n".join(lines)
