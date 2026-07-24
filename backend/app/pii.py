"""外发脱敏：诉求文本发往外部接口（检索/生成）前的最小化处理。
只脱与政策语义无关的强标识字段，不动姓名与小区名（保留检索语义）。"""
import re

_RULES = [
    (re.compile(r"\d{17}[\dXx]|\d{15}(?!\d)"), "[身份证号]"),
    (re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"), "[手机号]"),
    (re.compile(r"(?<!\d)0\d{2,3}-?\d{7,8}(?!\d)"), "[电话]"),
    (re.compile(r"(?<!\d)\d{16,19}(?!\d)"), "[卡号]"),
    (re.compile(r"[鲁苏豫皖冀晋京津沪浙粤湘鄂赣桂云贵川陕甘青琼辽吉黑蒙新藏宁渝][A-HJ-NP-Z][·\-]?[A-HJ-NP-Z0-9]{4,5}[挂学警港澳]?"), "[车牌号]"),
]

_ROOM = [
    (re.compile(r"\d+号楼"), "X号楼"),
    (re.compile(r"\d+单元"), "X单元"),
    (re.compile(r"\d+室"), "X室"),
]


def mask_for_external(text: str) -> str:
    """发往外部 API 前的脱敏（保留楼栋信息，检索可能用到小区层级语义）。"""
    if not text:
        return text
    for pat, rep in _RULES:
        text = pat.sub(rep, text)
    return text


def mask_for_display(text: str) -> str:
    """历史类案对一线展示时的脱敏（在外发级基础上再抹楼栋门牌）。"""
    text = mask_for_external(text)
    for pat, rep in _ROOM:
        text = pat.sub(rep, text)
    return text
