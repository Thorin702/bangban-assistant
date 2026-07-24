# -*- coding: utf-8 -*-
"""历史工单入库：解析 pg_dump → 展示级脱敏 → jieba 分词 → SQLite FTS5。

用法：python scripts/ingest_cases.py --sql /path/to/data_hotline_1.sql
产出：backend/data/cases.db（cases 表 + cases_fts 全文索引）
"""
import argparse
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import config  # noqa: E402
from app.pii import mask_for_display  # noqa: E402

COLS = ["id", "channel", "call_type", "c1", "c2", "c3", "c4", "c5", "desc", "location",
        "complainant", "gender", "phone", "entry_time", "t1", "u1", "t2", "u2", "t3", "u3",
        "return_unit", "return_time", "handling_unit", "handling", "reply_time",
        "revisit_time", "is_resolved", "is_satisfied", "is_overdue", "is_compliant", "is_assessed"]

SCHEMA = """
DROP TABLE IF EXISTS cases;
DROP TABLE IF EXISTS cases_fts;
CREATE TABLE cases(
  rowid INTEGER PRIMARY KEY,
  id INTEGER, call_type TEXT, c1 TEXT, c2 TEXT, c3 TEXT, c4 TEXT,
  location TEXT, entry_date TEXT,
  complaint TEXT, handling TEXT,
  is_resolved TEXT, is_satisfied TEXT, is_overdue TEXT, days INTEGER
);
CREATE VIRTUAL TABLE cases_fts USING fts5(tokens, content='');
"""


def unescape(s: str):
    if s == r"\N":
        return None
    return s.replace("\\n", "\n").replace("\\t", "\t").replace("\\r", "").replace("\\\\", "\\")


def clean(s):
    if not s:
        return s
    s = s.strip()
    if s.startswith('"') and s.endswith('"') and len(s) > 1:
        s = s[1:-1]
    return s.strip()


def _days_between(entry: str, reply: str):
    """办结天数 = 答复日期 - 受理日期（取日期部分，容错）。"""
    from datetime import date
    try:
        ed = date.fromisoformat((entry or "")[:10])
        rd = date.fromisoformat((reply or "")[:10])
        d = (rd - ed).days
        return d if 0 <= d <= 400 else None
    except (ValueError, TypeError):
        return None


def parse_rows(sql_path: str):
    with open(sql_path, encoding="utf-8", errors="replace") as f:
        in_copy = False
        for line in f:
            if line.startswith("COPY public.data_hotline_1"):
                in_copy = True
                continue
            if not in_copy:
                continue
            if line.strip() == "\\.":
                break
            parts = line.rstrip("\n").split("\t")
            if len(parts) != 31:
                continue
            r = dict(zip(COLS, (unescape(p) for p in parts)))
            desc = clean(r["desc"])
            if not desc or len(desc) < 10 or len(desc) > 3000 or "�" in desc:
                continue
            if r["location"] and len(r["location"]) > 200:
                continue
            handling = clean(r["handling"])
            if handling and (len(handling) < 15 or "�" in handling):
                handling = None
            complainant = (r["complainant"] or "").strip()
            desc_m = mask_for_display(desc)
            handling_m = mask_for_display(handling) if handling else None
            if complainant and len(complainant) >= 2:
                desc_m = desc_m.replace(complainant, "来电人")
                if handling_m:
                    handling_m = handling_m.replace(complainant, "来电人")
            yield {
                "id": int(r["id"]) if (r["id"] or "").isdigit() else None,
                "call_type": r["call_type"] or "",
                "c1": r["c1"] or "", "c2": r["c2"] or "", "c3": r["c3"] or "", "c4": r["c4"] or "",
                "location": (r["location"] or "").strip(),
                "entry_date": (r["entry_time"] or "")[:10],
                "complaint": desc_m,
                "handling": handling_m[:1500] if handling_m else None,
                "is_resolved": (r["is_resolved"] or "").strip(),
                "is_satisfied": (r["is_satisfied"] or "").strip(),
                "is_overdue": (r["is_overdue"] or "").strip(),
                "days": _days_between(r["entry_time"], r["reply_time"]),
            }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sql", required=True)
    args = ap.parse_args()

    import jieba
    jieba.initialize()

    t0 = time.time()
    conn = sqlite3.connect(config.CASES_DB)
    conn.executescript(SCHEMA)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=OFF")

    n = 0
    batch_rows, batch_fts = [], []
    for row in parse_rows(args.sql):
        n += 1
        # 检索文本 = 诉求 + 三级分类（分类词提升召回稳定性）
        fts_text = " ".join(jieba.cut(row["complaint"])) + " " + " ".join(
            x for x in (row["c1"], row["c2"], row["c3"], row["c4"]) if x)
        batch_rows.append((n, row["id"], row["call_type"], row["c1"], row["c2"], row["c3"], row["c4"],
                           row["location"], row["entry_date"], row["complaint"], row["handling"],
                           row["is_resolved"], row["is_satisfied"], row["is_overdue"], row["days"]))
        batch_fts.append((n, fts_text))
        if len(batch_rows) >= 2000:
            conn.executemany("INSERT INTO cases VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", batch_rows)
            conn.executemany("INSERT INTO cases_fts(rowid, tokens) VALUES(?,?)", batch_fts)
            conn.commit()
            batch_rows, batch_fts = [], []
            print(f"\r已入库 {n} 条…", end="", flush=True)
    if batch_rows:
        conn.executemany("INSERT INTO cases VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", batch_rows)
        conn.executemany("INSERT INTO cases_fts(rowid, tokens) VALUES(?,?)", batch_fts)
    conn.commit()
    conn.execute("INSERT INTO cases_fts(cases_fts) VALUES('optimize')")
    conn.commit()
    conn.close()
    print(f"\n完成：{n} 条 → {config.CASES_DB}（耗时 {time.time() - t0:.0f}s）")


if __name__ == "__main__":
    main()
