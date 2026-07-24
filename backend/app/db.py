"""SQLite 访问层：留痕即数据资产，schema 与《整体设计-v0.2》第六节一致。"""
import json
import sqlite3
from datetime import datetime, timezone, timedelta

from . import config

CST = timezone(timedelta(hours=8))

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  display_name TEXT NOT NULL,
  org TEXT DEFAULT '',
  role TEXT NOT NULL DEFAULT 'handler',
  status TEXT NOT NULL DEFAULT 'active',
  must_change_password INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  last_login_at TEXT
);
CREATE TABLE IF NOT EXISTS consults(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  complaint_text TEXT NOT NULL,
  complaint_masked TEXT NOT NULL,
  service_area TEXT DEFAULT '',
  eff_time TEXT DEFAULT '',
  status TEXT NOT NULL DEFAULT 'running',
  error_message TEXT,
  retrieval_json TEXT,
  cases_json TEXT,
  gen_text TEXT,
  sections_json TEXT,
  validation_json TEXT,
  experience_text TEXT,
  model TEXT,
  retrieval_mode TEXT,
  latency_ms INTEGER,
  first_token_ms INTEGER,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_consults_user ON consults(user_id, id DESC);
CREATE TABLE IF NOT EXISTS decisions(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  consult_id INTEGER NOT NULL,
  section TEXT NOT NULL,
  decision TEXT NOT NULL,
  modified_text TEXT,
  reason TEXT,
  created_at TEXT NOT NULL,
  UNIQUE(consult_id, section) ON CONFLICT REPLACE
);
CREATE TABLE IF NOT EXISTS audit_log(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER,
  username TEXT,
  action TEXT NOT NULL,
  detail TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings(
  key TEXT PRIMARY KEY,
  val TEXT NOT NULL
);
"""


def now_iso() -> str:
    return datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(config.APP_DB, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
        for stmt in ("ALTER TABLE consults ADD COLUMN research_json TEXT",):  # 增量迁移
            try:
                conn.execute(stmt)
            except sqlite3.OperationalError:
                pass
        for k, v in config.DEFAULT_SETTINGS.items():
            conn.execute("INSERT OR IGNORE INTO settings(key,val) VALUES(?,?)", (k, v))


# ---------- settings ----------

def get_settings() -> dict:
    with connect() as conn:
        rows = conn.execute("SELECT key,val FROM settings").fetchall()
    s = dict(config.DEFAULT_SETTINGS)
    s.update({r["key"]: r["val"] for r in rows})
    return s


def set_settings(pairs: dict) -> None:
    with connect() as conn:
        for k, v in pairs.items():
            conn.execute(
                "INSERT INTO settings(key,val) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET val=excluded.val",
                (k, str(v)),
            )


def setting_bool(s: dict, key: str) -> bool:
    return str(s.get(key, "0")).strip() in ("1", "true", "yes", "on")


def setting_int(s: dict, key: str, default: int) -> int:
    try:
        return max(1, int(str(s.get(key, default)).strip()))
    except ValueError:
        return default


def setting_lines(s: dict, key: str) -> list[str]:
    return [x.strip() for x in str(s.get(key, "")).splitlines() if x.strip()]


def mask_key(k: str) -> str:
    if not k:
        return ""
    if len(k) <= 8:
        return "••••"
    return k[:4] + "••••" + k[-4:]


# ---------- audit ----------

def audit(user_id, username, action: str, detail: str = "") -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO audit_log(user_id,username,action,detail,created_at) VALUES(?,?,?,?,?)",
            (user_id, username, action, detail[:500], now_iso()),
        )


# ---------- consults ----------

def create_consult(user_id: int, text: str, masked: str, area: str, eff: str,
                   retrieval_mode: str, model: str) -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO consults(user_id,complaint_text,complaint_masked,service_area,eff_time,"
            "status,retrieval_mode,model,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (user_id, text, masked, area, eff, "running", retrieval_mode, model, now_iso()),
        )
        return cur.lastrowid


def update_consult(cid: int, **fields) -> None:
    keys, vals = [], []
    for k, v in fields.items():
        if isinstance(v, (dict, list)):
            v = json.dumps(v, ensure_ascii=False)
        keys.append(f"{k}=?")
        vals.append(v)
    vals.append(cid)
    with connect() as conn:
        conn.execute(f"UPDATE consults SET {','.join(keys)} WHERE id=?", vals)


def get_consult(cid: int):
    with connect() as conn:
        return conn.execute("SELECT * FROM consults WHERE id=?", (cid,)).fetchone()


def consult_detail(row, with_user: bool = False) -> dict:
    d = {
        "id": row["id"],
        "complaint_text": row["complaint_text"],
        "service_area": row["service_area"],
        "eff_time": row["eff_time"],
        "status": row["status"],
        "error_message": row["error_message"],
        "retrieval": json.loads(row["retrieval_json"]) if row["retrieval_json"] else None,
        "cases": json.loads(row["cases_json"]) if row["cases_json"] else None,
        "research": json.loads(row["research_json"]) if ("research_json" in row.keys() and row["research_json"]) else None,
        "sections": json.loads(row["sections_json"]) if row["sections_json"] else None,
        "validation": json.loads(row["validation_json"]) if row["validation_json"] else None,
        "experience_text": row["experience_text"],
        "model": row["model"],
        "retrieval_mode": row["retrieval_mode"],
        "latency_ms": row["latency_ms"],
        "first_token_ms": row["first_token_ms"],
        "created_at": row["created_at"],
    }
    with connect() as conn:
        decs = conn.execute("SELECT section,decision,modified_text,reason,created_at FROM decisions WHERE consult_id=?", (row["id"],)).fetchall()
        d["decisions"] = {r["section"]: {"decision": r["decision"], "modified_text": r["modified_text"],
                                          "reason": r["reason"], "created_at": r["created_at"]} for r in decs}
        if with_user:
            u = conn.execute("SELECT username,display_name,org FROM users WHERE id=?", (row["user_id"],)).fetchone()
            d["user"] = dict(u) if u else None
    return d
