"""质量守卫：生成后的自动校验（只标注不改写，保可追溯）。"""
import re

# 优先匹配方括号格式；兼容模型偶尔输出的裸"材料N/案例N"（需紧跟数字，避免误伤"所需材料"等）
CITATION_RE = re.compile(r"[\[【〔]\s*(材料|案例)\s*(\d{1,2})\s*[\]】〕]|(材料|案例)(\d{1,2})")
DOCNO_RE = re.compile(r"[一-龥]{2,12}[〔\[（(](?:19|20)\d{2}[〕\]）)]\s*第?\s*\d{1,4}\s*号|国令第\d{1,4}号")
# 阈值型数值（温度/百分比）须出现在材料中，防"18℃"等常识性编造
THRESHOLD_NUM_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:℃|度|%)")
DOC_MARKERS = ["协议书", "调解协议", "此致", "敬礼", "特此证明", "兹有", "签字盖章", "（盖章）"]
SECTION_MARKERS = ["【条款解释】", "【回复话术】", "【办理方法】"]


def _norm_brackets(s: str) -> str:
    return s.translate(str.maketrans("[]（）()", "〔〕〔〕〔〕"))


def validate(gen_text: str, materials: list[dict], kind: str = "consult") -> dict:
    """返回 {issues:[{type,detail,section?}], citations:{total,invalid}, ok:bool}"""
    issues = []

    # 1) 角标有效性
    ref_word = "案例" if kind == "experience" else "材料"
    total, invalid = 0, []
    max_n = len(materials)
    for m in CITATION_RE.finditer(gen_text):
        word = m.group(1) or m.group(3)
        n = int(m.group(2) or m.group(4))
        if word != ref_word:
            continue
        total += 1
        if not (1 <= n <= max_n):
            invalid.append(n)
    if invalid:
        issues.append({"type": "citation_invalid",
                       "detail": f"出现无效角标 [{ref_word}{'/'.join(map(str, sorted(set(invalid))))}]（实际{ref_word}数为{max_n}）"})
    if total == 0 and max_n > 0 and len(gen_text) > 80:
        issues.append({"type": "citation_missing", "detail": "全文未标注任何来源角标"})

    # 2) 文号真实性（仅政策咨询）
    if kind == "consult":
        corpus = _norm_brackets(" ".join(
            (m.get("title") or "") + " " + (m.get("doc_no") or "") + " " +
            " ".join(s.get("content", "") for s in m.get("segments", []))
            for m in materials
        ))
        fake = []
        for m in DOCNO_RE.finditer(gen_text):
            doc = re.sub(r"\s+", "", m.group(0))
            if _norm_brackets(doc) not in re.sub(r"\s+", "", corpus):
                fake.append(doc)
        if fake:
            issues.append({"type": "docno_unverified",
                           "detail": "文号未见于检索材料，请核实：" + "、".join(sorted(set(fake)))})

        mat_nums = set(re.findall(r"\d+(?:\.\d+)?", corpus))
        bad_nums = [m.group(0) for m in THRESHOLD_NUM_RE.finditer(gen_text) if m.group(1) not in mat_nums]
        if bad_nums:
            issues.append({"type": "number_unverified",
                           "detail": "数值未见于检索材料，请核实：" + "、".join(sorted(set(bad_nums)))})

    # 3) 完整文书探测
    hits = [w for w in DOC_MARKERS if w in gen_text]
    if len(hits) >= 2 or ("甲方" in gen_text and "乙方" in gen_text):
        issues.append({"type": "document_like", "detail": "疑似生成完整文书要素（" + "、".join(hits[:4]) + "），已超出产品边界"})

    # 4) 结构完整性
    if kind == "consult":
        missing = [mk for mk in SECTION_MARKERS if mk not in gen_text]
        if missing:
            issues.append({"type": "structure_broken", "detail": "缺少输出部分标记：" + "、".join(missing)})

    return {"issues": issues, "citations": {"total": total, "invalid": sorted(set(invalid))}, "ok": not issues}
