"""业务路由：认证 / 咨询（SSE）/ 决策留痕 / 历史。"""
import time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from . import auth, cases, db, generation, pipeline

router = APIRouter(prefix="/api")

SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"}


# ---------- 认证 ----------

class LoginBody(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


# 简易登录失败限流（单进程内存，防在线爆破）：同一账号 5 分钟内失败 ≥8 次锁定
_login_fail: dict[str, list] = {}
_LOGIN_MAX, _LOGIN_WINDOW = 8, 300


def _login_throttled(key: str) -> bool:
    c = _login_fail.get(key)
    return bool(c and time.time() - c[1] < _LOGIN_WINDOW and c[0] >= _LOGIN_MAX)


def _login_record_fail(key: str) -> None:
    now = time.time()
    c = _login_fail.get(key)
    if not c or now - c[1] >= _LOGIN_WINDOW:
        _login_fail[key] = [1, now]
    else:
        c[0] += 1


@router.post("/auth/login")
def login(body: LoginBody):
    key = body.username.strip().lower()
    if _login_throttled(key):
        raise HTTPException(429, "登录尝试过于频繁，请 5 分钟后再试")
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE username=?", (body.username.strip(),)).fetchone()
    if not row or not auth.verify_password(body.password, row["password_hash"]):
        _login_record_fail(key)
        db.audit(None, body.username[:64], "login_failed", "口令或账号错误")
        raise HTTPException(401, "账号或密码错误")
    if row["status"] != "active":
        raise HTTPException(403, "账号已停用，请联系管理员")
    _login_fail.pop(key, None)  # 成功清零
    with db.connect() as conn:
        conn.execute("UPDATE users SET last_login_at=? WHERE id=?", (db.now_iso(), row["id"]))
    db.audit(row["id"], row["username"], "login", "")
    return {"token": auth.issue_token(row["id"]), "user": auth.user_public(row)}


class ChangePwBody(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8, max_length=64)


@router.post("/auth/change-password")
def change_password(body: ChangePwBody, user=Depends(auth.current_user)):
    if not auth.verify_password(body.old_password, user["password_hash"]):
        raise HTTPException(400, "原密码不正确")
    if body.new_password == body.old_password:
        raise HTTPException(400, "新密码不能与原密码相同")
    with db.connect() as conn:
        conn.execute("UPDATE users SET password_hash=?, must_change_password=0 WHERE id=?",
                     (auth.hash_password(body.new_password), user["id"]))
    db.audit(user["id"], user["username"], "change_password", "")
    return {"ok": True}


@router.get("/auth/me")
def me(user=Depends(auth.current_user)):
    return auth.user_public(user)


# ---------- 全局配置（前端渲染用）----------

@router.get("/config")
def app_config(user=Depends(auth.current_user)):
    s = db.get_settings()
    cfg = generation.resolve_config(s)
    return {
        "case_feature_enabled": db.setting_bool(s, "case_feature_enabled") and cases.available(),
        "research_enabled": db.setting_bool(s, "research_enabled") and cases.available(),
        "disclaimer_text": s.get("disclaimer_text", ""),
        "service_area": s.get("default_service_area", ""),
        "llm_ready": generation.is_configured(cfg),
    }


# ---------- 咨询 ----------

class ConsultBody(BaseModel):
    complaint_text: str = Field(min_length=10, max_length=2000)


@router.post("/consults")
def create_consult(body: ConsultBody, user=Depends(auth.current_user)):
    gen = pipeline.run_consult(user, body.complaint_text.strip())
    return StreamingResponse(gen, media_type="text/event-stream", headers=SSE_HEADERS)


@router.post("/consults/{cid}/experience")
def consult_experience(cid: int, user=Depends(auth.current_user)):
    row = db.get_consult(cid)
    if not row or (row["user_id"] != user["id"] and user["role"] != "admin"):
        raise HTTPException(404, "咨询记录不存在")
    gen = pipeline.run_experience(user, row)
    return StreamingResponse(gen, media_type="text/event-stream", headers=SSE_HEADERS)


@router.post("/consults/{cid}/prescription")
def consult_prescription(cid: int, user=Depends(auth.current_user)):
    row = db.get_consult(cid)
    if not row or (row["user_id"] != user["id"] and user["role"] != "admin"):
        raise HTTPException(404, "咨询记录不存在")
    gen = pipeline.run_prescription(user, row)
    return StreamingResponse(gen, media_type="text/event-stream", headers=SSE_HEADERS)


class DecisionBody(BaseModel):
    section: str
    decision: str
    modified_text: str | None = None
    reason: str | None = None


@router.post("/consults/{cid}/decisions")
def record_decision(cid: int, body: DecisionBody, user=Depends(auth.current_user)):
    if body.section not in ("interpret", "reply", "method", "experience"):
        raise HTTPException(400, "无效的部分标识")
    if body.decision not in ("adopt", "modify", "reject"):
        raise HTTPException(400, "无效的决策类型")
    row = db.get_consult(cid)
    if not row or row["user_id"] != user["id"]:
        raise HTTPException(404, "咨询记录不存在")
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO decisions(consult_id,section,decision,modified_text,reason,created_at) VALUES(?,?,?,?,?,?)",
            (cid, body.section, body.decision, body.modified_text, body.reason, db.now_iso()),
        )
    return {"ok": True}


@router.get("/consults")
def list_consults(page: int = 1, size: int = 20, user=Depends(auth.current_user)):
    page, size = max(1, page), min(max(1, size), 50)
    with db.connect() as conn:
        total = conn.execute("SELECT COUNT(*) c FROM consults WHERE user_id=?", (user["id"],)).fetchone()["c"]
        rows = conn.execute(
            "SELECT id, complaint_text, service_area, status, created_at, latency_ms FROM consults "
            "WHERE user_id=? ORDER BY id DESC LIMIT ? OFFSET ?",
            (user["id"], size, (page - 1) * size),
        ).fetchall()
        ids = [r["id"] for r in rows]
        dec_map = {}
        if ids:
            q = ",".join("?" * len(ids))
            for d in conn.execute(f"SELECT consult_id, section, decision FROM decisions WHERE consult_id IN ({q})", ids):
                dec_map.setdefault(d["consult_id"], {})[d["section"]] = d["decision"]
    items = [{
        "id": r["id"],
        "excerpt": r["complaint_text"][:60] + ("…" if len(r["complaint_text"]) > 60 else ""),
        "service_area": r["service_area"], "status": r["status"],
        "created_at": r["created_at"], "latency_ms": r["latency_ms"],
        "decisions": dec_map.get(r["id"], {}),
    } for r in rows]
    return {"total": total, "page": page, "size": size, "items": items}


@router.get("/consults/{cid}")
def consult_detail(cid: int, user=Depends(auth.current_user)):
    row = db.get_consult(cid)
    if not row or (row["user_id"] != user["id"] and user["role"] != "admin"):
        raise HTTPException(404, "咨询记录不存在")
    return db.consult_detail(row, with_user=(user["role"] == "admin"))
