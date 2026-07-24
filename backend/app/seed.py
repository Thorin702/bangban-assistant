"""初始化管理员账号：python -m app.seed [--demo]"""
import sys

from . import auth, db


def main():
    db.init_db()
    created = []
    with db.connect() as conn:
        if not conn.execute("SELECT 1 FROM users WHERE username='admin'").fetchone():
            pw = auth.gen_temp_password()
            conn.execute(
                "INSERT INTO users(username,password_hash,display_name,org,role,status,must_change_password,created_at)"
                " VALUES('admin',?,?,?,?,?,1,?)",
                (auth.hash_password(pw), "系统管理员", "平台运营", "admin", "active", db.now_iso()),
            )
            created.append(("admin", pw))
        if "--demo" in sys.argv and not conn.execute("SELECT 1 FROM users WHERE username='demo01'").fetchone():
            pw = auth.gen_temp_password()
            conn.execute(
                "INSERT INTO users(username,password_hash,display_name,org,role,status,must_change_password,created_at)"
                " VALUES('demo01',?,?,?,?,?,1,?)",
                (auth.hash_password(pw), "演示承办人", "市中区政务服务中心", "handler", "active", db.now_iso()),
            )
            created.append(("demo01", pw))
    if created:
        print("已创建账号（首次登录须改密）：")
        for u, p in created:
            print(f"  {u} / {p}")
    else:
        print("账号已存在，未做变更。")


if __name__ == "__main__":
    main()
