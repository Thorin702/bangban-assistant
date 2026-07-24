"""账号与鉴权：scrypt 口令散列（标准库）+ JWT 会话。"""
import hashlib
import secrets
import time

import jwt
from fastapi import Depends, HTTPException, Request

from . import config, db


# ---------- 口令 ----------

def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    h = hashlib.scrypt(pw.encode(), salt=salt, n=2 ** 14, r=8, p=1)
    return salt.hex() + "$" + h.hex()


def verify_password(pw: str, stored: str) -> bool:
    try:
        salt_hex, h_hex = stored.split("$")
        h = hashlib.scrypt(pw.encode(), salt=bytes.fromhex(salt_hex), n=2 ** 14, r=8, p=1)
        return secrets.compare_digest(h.hex(), h_hex)
    except Exception:
        return False


def gen_temp_password() -> str:
    # 可读性优先的临时口令：4位字母段-4位数字段
    letters = "abcdefghjkmnpqrstuvwxyz"
    return "".join(secrets.choice(letters) for _ in range(4)) + "-" + str(secrets.randbelow(9000) + 1000)


# ---------- JWT ----------

def issue_token(user_id: int) -> str:
    payload = {"uid": user_id, "iat": int(time.time()),
               "exp": int(time.time()) + config.JWT_TTL_HOURS * 3600}
    return jwt.encode(payload, config.JWT_SECRET, algorithm="HS256")


def _decode(token: str) -> int:
    try:
        payload = jwt.decode(token, config.JWT_SECRET, algorithms=["HS256"])
        return int(payload["uid"])
    except Exception:
        raise HTTPException(401, "登录已失效，请重新登录")


def user_public(row) -> dict:
    return {"id": row["id"], "username": row["username"], "display_name": row["display_name"],
            "org": row["org"], "role": row["role"], "status": row["status"],
            "must_change_password": bool(row["must_change_password"]),
            "created_at": row["created_at"], "last_login_at": row["last_login_at"]}


# 未完成首登改密时，仅放行以下接口，其余一律 403（服务端强制，不只靠前端）
_MUST_CHANGE_ALLOW = {"/api/auth/change-password", "/api/auth/me", "/api/config"}


def current_user(request: Request):
    authz = request.headers.get("Authorization", "")
    token = authz[7:] if authz.startswith("Bearer ") else ""  # 仅接受请求头，不从 URL 取，避免令牌进日志
    if not token:
        raise HTTPException(401, "未登录")
    uid = _decode(token)
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    if not row or row["status"] != "active":
        raise HTTPException(401, "账号不可用")
    if row["must_change_password"] and request.url.path not in _MUST_CHANGE_ALLOW:
        raise HTTPException(403, "请先修改初始密码后再使用")
    return row


def require_admin(user=Depends(current_user)):
    if user["role"] != "admin":
        raise HTTPException(403, "需要管理员权限")
    return user
