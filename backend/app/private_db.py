"""私有政策库（可选）：各地市/区不公开的政策法规，导入后经简单治理，
与 dknowc 一样参与检索。分段治理 + jieba 分词 + SQLite FTS5 关键词检索。"""
import json
import re
import sqlite3
import threading

from . import config, db

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None

_STOP = set("的了和及与或对在为以按其该等")

SCHEMA = """
CREATE TABLE IF NOT EXISTS pdocs(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL, doc_no TEXT, date TEXT, source TEXT, region TEXT,
  segments_json TEXT NOT NULL, seg_count INTEGER, created_at TEXT
);
CREATE VIRTUAL TABLE IF NOT EXISTS pdocs_fts USING fts5(tokens);
"""


def _connect() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(config.PRIVATE_DB, check_same_thread=False, timeout=30)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.executescript(SCHEMA)
    return _conn


def init() -> None:
    with _lock:
        _connect()


def available() -> bool:
    with _lock:
        c = _connect()
        return c.execute("SELECT COUNT(*) n FROM pdocs").fetchone()["n"] > 0


def stats() -> dict:
    with _lock:
        c = _connect()
        row = c.execute("SELECT COUNT(*) n, COALESCE(SUM(seg_count),0) s FROM pdocs").fetchone()
    return {"doc_count": row["n"], "segment_count": row["s"]}


def _segment(content: str) -> list[dict]:
    """治理：按空行分段，过长段落按句号再切到 ~300 字；每段作为一个可检索/引用单元。"""
    segs = []
    for para in re.split(r"\n\s*\n", content or ""):
        para = re.sub(r"[ \t]+", " ", para).strip()
        if not para:
            continue
        title = ""
        m = re.match(r"^(第[一二三四五六七八九十百零]+条|[一二三四五六七八九十]+、)", para)
        if m:
            title = m.group(1)
        if len(para) <= 400:
            if len(para) >= 8:
                segs.append({"title": title, "content": para})
        else:
            buf = ""
            for part in re.split(r"(。|；)", para):
                buf += part
                if len(buf) >= 280:
                    segs.append({"title": title, "content": buf.strip()})
                    buf, title = "", ""
            if len(buf.strip()) >= 8:
                segs.append({"title": title, "content": buf.strip()})
    return segs


def ingest(title: str, doc_no: str, date: str, source: str, region: str, content: str) -> dict:
    import jieba
    title = (title or "").strip()
    content = (content or "").strip()
    if not title or not content:
        raise ValueError("标题与正文不能为空")
    # 正文首行与标题重复时去重，避免标题被当作段落
    lines = content.split("\n", 1)
    if lines and lines[0].strip() == title and len(lines) > 1:
        content = lines[1].strip()
    segs = _segment(content)
    if not segs:
        raise ValueError("正文治理后无有效段落，请检查内容")
    tokens = " ".join(jieba.cut(title + "。" + content))
    with _lock:
        c = _connect()
        cur = c.execute(
            "INSERT INTO pdocs(title,doc_no,date,source,region,segments_json,seg_count,created_at)"
            " VALUES(?,?,?,?,?,?,?,?)",
            (title, doc_no.strip(), date.strip(), source.strip() or "本地政策库", region.strip(),
             json.dumps(segs, ensure_ascii=False), len(segs), db.now_iso()),
        )
        c.execute("INSERT INTO pdocs_fts(rowid, tokens) VALUES(?,?)", (cur.lastrowid, tokens))
        c.commit()
    return {"id": cur.lastrowid, "seg_count": len(segs)}


def list_docs() -> list[dict]:
    with _lock:
        c = _connect()
        rows = c.execute(
            "SELECT id,title,doc_no,date,source,region,seg_count,created_at FROM pdocs ORDER BY id DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def delete(doc_id: int) -> bool:
    with _lock:
        c = _connect()
        r = c.execute("DELETE FROM pdocs WHERE id=?", (doc_id,))
        c.execute("DELETE FROM pdocs_fts WHERE rowid=?", (doc_id,))
        c.commit()
        return r.rowcount > 0


def _keywords(text: str, top_k: int = 12) -> list[str]:
    import jieba.analyse
    kws = [k for k in jieba.analyse.extract_tags(text, topK=top_k) if len(k) >= 2 and k not in _STOP]
    return kws


def search(query: str, top_k: int = 3, segment_count: int = 3) -> list[dict]:
    """返回统一材料结构，标记 private=True、authoritative=True。"""
    if not available():
        return []
    kws = _keywords(query)
    if not kws:
        return []
    match = " OR ".join('"' + k.replace('"', "") + '"' for k in kws)
    with _lock:
        c = _connect()
        try:
            rows = c.execute(
                "SELECT d.*, bm25(pdocs_fts) AS rank FROM pdocs_fts "
                "JOIN pdocs d ON d.id = pdocs_fts.rowid "
                "WHERE pdocs_fts MATCH ? ORDER BY rank LIMIT ?",
                (match, top_k),
            ).fetchall()
        except sqlite3.OperationalError:
            return []
    materials = []
    for r in rows:
        segs = json.loads(r["segments_json"])
        # 段落层面按关键词命中度粗排，取最相关的前 segment_count 段
        segs.sort(key=lambda s: sum(1 for k in kws if k in s["content"]), reverse=True)
        materials.append({
            "title": r["title"],
            "source": r["source"] or "本地政策库",
            "url": "",
            "region": r["region"] or "",
            "date": r["date"] or "",
            "reliability": "高",
            "doc_no": r["doc_no"] or "",
            "segments": segs[: max(segment_count, 1)],
            "authoritative": True,
            "private": True,
        })
    return materials
