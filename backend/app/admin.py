"""后台管理 API：概览指标 / 用户管理 / 功能与参数 / 咨询记录 / 审计日志。"""
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from . import auth, cases, config, db, generation, geo_data, private_db

router = APIRouter(prefix="/api/admin", dependencies=[Depends(auth.require_admin)])

EDITABLE_KEYS = {
    "llm_base_url", "llm_model",
    "gen_temperature", "gen_top_p", "gen_max_tokens", "gen_enable_thinking", "gen_extra_params",
    "consult_system_prompt", "experience_system_prompt",
    "case_feature_enabled", "case_top_k",
    "research_enabled",
    "private_db_enabled",
    "default_service_area", "default_eff_time",
    "top_n", "segment_count",
    "blocked_source_keywords", "authoritative_domains", "authoritative_source_names",
    "disclaimer_text",
}
INT_KEYS = {"top_n", "segment_count", "gen_max_tokens", "case_top_k"}
FLOAT_KEYS = {"gen_temperature", "gen_top_p"}


# ---------- 概览指标 ----------

@router.get("/metrics")
def metrics():
    with db.connect() as conn:
        total = conn.execute("SELECT COUNT(*) c FROM consults").fetchone()["c"]
        week = conn.execute("SELECT COUNT(*) c FROM consults WHERE created_at >= datetime('now','localtime','-7 day')").fetchone()["c"]
        by_status = {r["status"]: r["c"] for r in conn.execute("SELECT status, COUNT(*) c FROM consults GROUP BY status")}
        users_active = conn.execute("SELECT COUNT(DISTINCT user_id) c FROM consults WHERE created_at >= datetime('now','localtime','-7 day')").fetchone()["c"]
        lat = conn.execute("SELECT AVG(latency_ms) a, AVG(first_token_ms) f FROM consults WHERE status='done'").fetchone()
        daily = conn.execute(
            "SELECT substr(created_at,1,10) d, COUNT(*) c FROM consults "
            "WHERE created_at >= datetime('now','localtime','-14 day') GROUP BY d ORDER BY d"
        ).fetchall()
        dec = conn.execute("SELECT section, decision, COUNT(*) c FROM decisions GROUP BY section, decision").fetchall()
        viol = conn.execute(
            "SELECT id, created_at, validation_json FROM consults "
            "WHERE validation_json IS NOT NULL AND validation_json NOT LIKE '%\"issues\": []%' "
            "ORDER BY id DESC LIMIT 10"
        ).fetchall()
        viol_count = conn.execute(
            "SELECT COUNT(*) c FROM consults WHERE validation_json IS NOT NULL AND validation_json NOT LIKE '%\"issues\": []%'"
        ).fetchone()["c"]

    decisions = {}
    for r in dec:
        decisions.setdefault(r["section"], {})[r["decision"]] = r["c"]
    import json as _json
    violations = []
    for r in viol:
        try:
            issues = _json.loads(r["validation_json"]).get("issues", [])
        except Exception:
            issues = []
        if issues:
            violations.append({"consult_id": r["id"], "created_at": r["created_at"], "issues": issues})
    done = by_status.get("done", 0)
    return {
        "total_consults": total, "week_consults": week, "by_status": by_status,
        "active_users_7d": users_active,
        "avg_latency_ms": int(lat["a"] or 0), "avg_first_token_ms": int(lat["f"] or 0),
        "empty_rate": round(by_status.get("empty", 0) / total, 3) if total else 0,
        "error_rate": round(by_status.get("error", 0) / total, 3) if total else 0,
        "violation_count": viol_count,
        "violation_rate": round(viol_count / done, 3) if done else 0,
        "daily": [{"date": r["d"], "count": r["c"]} for r in daily],
        "decisions": decisions,
        "recent_violations": violations,
    }


# ---------- 用户管理 ----------

@router.get("/users")
def list_users():
    with db.connect() as conn:
        rows = conn.execute("SELECT * FROM users ORDER BY id").fetchall()
    return [auth.user_public(r) for r in rows]


class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=32, pattern=r"^[a-zA-Z0-9_\-]+$")
    display_name: str = Field(min_length=1, max_length=32)
    org: str = ""
    role: str = "handler"


@router.post("/users")
def create_user(body: UserCreate, admin=Depends(auth.require_admin)):
    if body.role not in ("handler", "mediator", "admin"):
        raise HTTPException(400, "无效角色")
    temp_pw = auth.gen_temp_password()
    try:
        with db.connect() as conn:
            conn.execute(
                "INSERT INTO users(username,password_hash,display_name,org,role,status,must_change_password,created_at)"
                " VALUES(?,?,?,?,?,?,1,?)",
                (body.username.strip(), auth.hash_password(temp_pw), body.display_name.strip(),
                 body.org.strip(), body.role, "active", db.now_iso()),
            )
    except Exception:
        raise HTTPException(400, "用户名已存在")
    db.audit(admin["id"], admin["username"], "create_user", body.username)
    return {"ok": True, "temp_password": temp_pw}


@router.post("/users/{uid}/reset-password")
def reset_password(uid: int, admin=Depends(auth.require_admin)):
    temp_pw = auth.gen_temp_password()
    with db.connect() as conn:
        row = conn.execute("SELECT username FROM users WHERE id=?", (uid,)).fetchone()
        if not row:
            raise HTTPException(404, "用户不存在")
        conn.execute("UPDATE users SET password_hash=?, must_change_password=1 WHERE id=?",
                     (auth.hash_password(temp_pw), uid))
    db.audit(admin["id"], admin["username"], "reset_password", row["username"])
    return {"ok": True, "temp_password": temp_pw}


class StatusBody(BaseModel):
    status: str


@router.post("/users/{uid}/status")
def set_user_status(uid: int, body: StatusBody, admin=Depends(auth.require_admin)):
    if body.status not in ("active", "disabled"):
        raise HTTPException(400, "无效状态")
    if uid == admin["id"]:
        raise HTTPException(400, "不能停用自己的账号")
    with db.connect() as conn:
        row = conn.execute("SELECT username FROM users WHERE id=?", (uid,)).fetchone()
        if not row:
            raise HTTPException(404, "用户不存在")
        conn.execute("UPDATE users SET status=? WHERE id=?", (body.status, uid))
    db.audit(admin["id"], admin["username"], "set_user_status", f"{row['username']} -> {body.status}")
    return {"ok": True}


# ---------- 功能与参数 ----------

@router.get("/settings")
def get_settings():
    s = db.get_settings()
    cfg = generation.resolve_config(s)
    return {
        "settings": {k: s.get(k, "") for k in EDITABLE_KEYS},
        "llm": {
            "api_key_set": bool(s.get("llm_api_key")),
            "api_key_hint": db.mask_key(s.get("llm_api_key", "")),
        },
        "runtime": {
            "retrieval_mode": "mock" if config.RETRIEVAL_MOCK else "live",
            "retrieval_endpoint": config.DKNOWC_ENDPOINT,
            "llm_ready": generation.is_configured(cfg),
            "cases": cases.stats(),
            "private": private_db.stats(),
        },
    }


class SettingsBody(BaseModel):
    settings: dict
    llm_api_key: str | None = None


@router.put("/settings")
def put_settings(body: SettingsBody, admin=Depends(auth.require_admin)):
    pairs = {}
    for k, v in body.settings.items():
        if k not in EDITABLE_KEYS:
            raise HTTPException(400, f"不可编辑的配置项：{k}")
        val = str(v)
        if k in INT_KEYS and (not val.strip().isdigit() or int(val) < 1):
            raise HTTPException(400, f"{k} 须为正整数")
        if k in FLOAT_KEYS:
            try:
                float(val)
            except ValueError:
                raise HTTPException(400, f"{k} 须为数字")
        if k == "default_service_area":
            norm = geo_data.normalize_city(val)
            if not norm:
                raise HTTPException(400, f"「{val or '空'}」不是有效的地市级名称，请输入地级市/自治州/地区（如：枣庄、临沂、呼伦贝尔）")
            val = norm  # 存规范化核心名，供检索地域过滤与生成注入使用
        if k == "gen_extra_params" and val.strip():
            try:
                if not isinstance(json.loads(val), dict):
                    raise ValueError
            except (json.JSONDecodeError, ValueError):
                raise HTTPException(400, "扩展参数须为合法的 JSON 对象（如 {\"presence_penalty\": 0.2}）")
        pairs[k] = val
    changed = list(pairs.keys())
    if body.llm_api_key:  # 仅在填入新 Key 时更新，留空表示保持不变
        pairs["llm_api_key"] = body.llm_api_key.strip()
        changed.append("llm_api_key")
    if pairs:
        db.set_settings(pairs)
    db.audit(admin["id"], admin["username"], "update_settings", ",".join(changed))
    return {"ok": True}


@router.get("/cities")
def cities_list():
    """全国地市级预置库（供前端输入联想与校验参考）。"""
    return {"cities": sorted(geo_data.ALL_PREFECTURES)}


@router.get("/private-docs")
def private_docs_list():
    return {"stats": private_db.stats(), "docs": private_db.list_docs()}


class PrivateDocBody(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=10)
    doc_no: str = ""
    date: str = ""
    source: str = ""
    region: str = ""


@router.post("/private-docs")
def private_docs_add(body: PrivateDocBody, admin=Depends(auth.require_admin)):
    try:
        r = private_db.ingest(body.title, body.doc_no, body.date, body.source, body.region, body.content)
    except ValueError as e:
        raise HTTPException(400, str(e))
    db.audit(admin["id"], admin["username"], "private_doc_add", f"{body.title}（{r['seg_count']}段）")
    return {"ok": True, **r}


@router.delete("/private-docs/{doc_id}")
def private_docs_delete(doc_id: int, admin=Depends(auth.require_admin)):
    if not private_db.delete(doc_id):
        raise HTTPException(404, "文档不存在")
    db.audit(admin["id"], admin["username"], "private_doc_delete", str(doc_id))
    return {"ok": True}


class LLMTestBody(BaseModel):
    base_url: str = ""
    model: str = ""
    api_key: str = ""


@router.post("/llm/test")
def llm_test(body: LLMTestBody, admin=Depends(auth.require_admin)):
    s = db.get_settings()
    base = body.base_url.strip() or s.get("llm_base_url", "")
    model = body.model.strip() or s.get("llm_model", "")
    key = body.api_key.strip() or s.get("llm_api_key", "")
    result = generation.test_connection(base, key, model)
    db.audit(admin["id"], admin["username"], "llm_test", f"{model}：{'成功' if result.get('ok') else '失败'}")
    return result


# ---------- 咨询记录（全量）----------

@router.get("/consults")
def all_consults(page: int = 1, size: int = 20, status: str = "", username: str = "", q: str = ""):
    page, size = max(1, page), min(max(1, size), 50)
    where, args = [], []
    if status:
        where.append("c.status=?")
        args.append(status)
    if username:
        where.append("u.username LIKE ?")
        args.append(f"%{username}%")
    if q:
        where.append("c.complaint_text LIKE ?")
        args.append(f"%{q}%")
    cond = ("WHERE " + " AND ".join(where)) if where else ""
    with db.connect() as conn:
        total = conn.execute(f"SELECT COUNT(*) c FROM consults c JOIN users u ON u.id=c.user_id {cond}", args).fetchone()["c"]
        rows = conn.execute(
            f"SELECT c.id, c.complaint_text, c.status, c.created_at, c.latency_ms, c.retrieval_mode, c.model,"
            f" u.username, u.display_name FROM consults c JOIN users u ON u.id=c.user_id {cond}"
            f" ORDER BY c.id DESC LIMIT ? OFFSET ?", args + [size, (page - 1) * size],
        ).fetchall()
        ids = [r["id"] for r in rows]
        dec_map = {}
        if ids:
            qm = ",".join("?" * len(ids))
            for d in conn.execute(f"SELECT consult_id, section, decision FROM decisions WHERE consult_id IN ({qm})", ids):
                dec_map.setdefault(d["consult_id"], {})[d["section"]] = d["decision"]
    return {"total": total, "page": page, "size": size, "items": [{
        "id": r["id"], "excerpt": r["complaint_text"][:50] + ("…" if len(r["complaint_text"]) > 50 else ""),
        "status": r["status"], "created_at": r["created_at"], "latency_ms": r["latency_ms"],
        "retrieval_mode": r["retrieval_mode"], "model": r["model"],
        "username": r["username"], "display_name": r["display_name"],
        "decisions": dec_map.get(r["id"], {}),
    } for r in rows]}


# ---------- 审计日志 ----------

@router.get("/audit")
def audit_log(page: int = 1, size: int = 30):
    page, size = max(1, page), min(max(1, size), 100)
    with db.connect() as conn:
        total = conn.execute("SELECT COUNT(*) c FROM audit_log").fetchone()["c"]
        rows = conn.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT ? OFFSET ?",
                            (size, (page - 1) * size)).fetchall()
    return {"total": total, "page": page, "size": size,
            "items": [dict(r) for r in rows]}
