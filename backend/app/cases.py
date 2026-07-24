"""类案检索（M2，后台可开关）：本地历史工单 SQLite FTS5 + jieba 关键词 + bm25 排序。
数据由 scripts/ingest_cases.py 一次性入库（入库时已完成展示级脱敏）。"""
import re
import sqlite3
import threading

from . import config

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None

_STOP = set("来电人反映本人要求咨询前期尽快相关部门处理解决协调告知因导致现至今多次未果并且但是")


def available() -> bool:
    return config.CASES_DB.exists()


def _get_conn() -> sqlite3.Connection:
    global _conn
    with _lock:
        if _conn is None:
            _conn = sqlite3.connect(f"file:{config.CASES_DB}?mode=ro", uri=True, check_same_thread=False)
            _conn.row_factory = sqlite3.Row
        return _conn


def stats() -> dict:
    if not available():
        return {"available": False, "count": 0, "date_range": None}
    conn = _get_conn()
    with _lock:  # 与其他查询共用单连接，须串行化
        row = conn.execute("SELECT COUNT(*) c, MIN(entry_date) a, MAX(entry_date) b FROM cases").fetchone()
    return {"available": True, "count": row["c"], "date_range": [row["a"], row["b"]]}


def _keywords(text: str, top_k: int = 12) -> list[str]:
    import jieba.analyse
    kws = jieba.analyse.extract_tags(text, topK=top_k)
    kws = [k for k in kws if len(k) >= 2 and k not in _STOP and not k.isdigit()]
    if not kws:  # 兜底：连续汉字二元组
        han = re.findall(r"[一-龥]{2,}", text)
        kws = list({w[i:i + 2] for w in han for i in range(0, len(w) - 1)})[:top_k]
    return kws[:top_k]


def search_similar(query: str, top_k: int = 5) -> list[dict]:
    """返回 [{n, case_id, complaint, handling, category, location, entry_date, is_resolved, is_satisfied, score}]"""
    if not available():
        return []
    kws = _keywords(query)
    if not kws:
        return []
    match = " OR ".join('"' + k.replace('"', "") + '"' for k in kws)
    conn = _get_conn()
    with _lock:
        try:
            rows = conn.execute(
                "SELECT c.*, bm25(cases_fts) AS rank FROM cases_fts "
                "JOIN cases c ON c.rowid = cases_fts.rowid "
                "WHERE cases_fts MATCH ? ORDER BY rank LIMIT ?",
                (match, max(top_k * 4, 20)),
            ).fetchall()
        except sqlite3.OperationalError:
            return []
    # 轻量重排：bm25 基础上按关键词覆盖率微调，并去近重复（同类目同前缀）
    results, seen = [], set()
    for r in rows:
        text = r["complaint"] or ""
        cover = sum(1 for k in kws if k in text) / max(len(kws), 1)
        key = (r["c2"] or "") + text[:24]
        if key in seen:
            continue
        seen.add(key)
        results.append((cover, -float(r["rank"]), r))
    results.sort(key=lambda x: (round(x[0], 2), x[1]), reverse=True)
    out = []
    for i, (cover, _neg_rank, r) in enumerate(results[:top_k], 1):
        category = " / ".join(x for x in (r["c1"], r["c2"], r["c3"]) if x)
        out.append({
            "n": i,
            "case_id": r["id"],
            "complaint": r["complaint"],
            "handling": r["handling"],
            "category": category,
            "location": r["location"] or "",
            "entry_date": r["entry_date"] or "",
            "is_resolved": r["is_resolved"] or "",
            "is_satisfied": r["is_satisfied"] or "",
            "match": round(min(cover, 1.0), 2),
        })
    return out


def research_rows(query: str, limit: int = 60) -> list[dict]:
    """办件研判取样：返回一批同类工单（含时限/超期/满意度字段）用于统计。"""
    if not available():
        return []
    kws = _keywords(query)
    if not kws:
        return []
    match = " OR ".join('"' + k.replace('"', "") + '"' for k in kws)
    conn = _get_conn()
    with _lock:
        try:
            rows = conn.execute(
                "SELECT c.c1,c.c2,c.c3,c.location,c.entry_date,c.complaint,c.handling,"
                "c.is_resolved,c.is_satisfied,c.is_overdue,c.days FROM cases_fts "
                "JOIN cases c ON c.rowid = cases_fts.rowid "
                "WHERE cases_fts MATCH ? ORDER BY rank LIMIT ?",
                (match, limit),
            ).fetchall()
        except sqlite3.OperationalError:
            return []
    return [dict(r) for r in rows]


def related_by_community(community: str, category2: str = "", limit: int = 6) -> dict:
    """关联研判：同小区（可选同二级分类）历史同类工单数与样例。"""
    if not available() or not community:
        return {"count": 0, "cases": []}
    conn = _get_conn()
    # 小区名多在诉求正文里（location 常为区县级），故同时匹配 complaint 与 location
    sql = "SELECT complaint, entry_date, c2, is_resolved, is_satisfied FROM cases WHERE (complaint LIKE ? OR location LIKE ?)"
    args = [f"%{community}%", f"%{community}%"]
    if category2:
        sql += " AND c2 = ?"
        args.append(category2)
    sql += " ORDER BY entry_date DESC"
    with _lock:
        rows = conn.execute(sql, args).fetchall()
    return {
        "count": len(rows),
        "cases": [{"complaint": r["complaint"], "entry_date": r["entry_date"] or "",
                   "category": r["c2"] or "", "is_resolved": r["is_resolved"] or "",
                   "is_satisfied": r["is_satisfied"] or ""} for r in rows[:limit]],
    }
