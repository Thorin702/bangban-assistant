"""应用入口：API + 前端静态托管（同源，无跨域）。"""
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import admin, config, db, private_db, routes

app = FastAPI(title="基层帮办智能助手", docs_url=None, redoc_url=None)
db.init_db()
private_db.init()

app.include_router(routes.router)
app.include_router(admin.router)


@app.get("/api/health")
def health():
    return {"ok": True}


# 前端构建产物（frontend build → backend/static）
if config.STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=config.STATIC_DIR / "assets"), name="assets")
    _STATIC_ROOT = config.STATIC_DIR.resolve()

    @app.get("/{path:path}")
    def spa(path: str):
        # 仅返回 static 目录内的真实文件；越界一律回退 index.html（防路径穿越）
        if path:
            target = (_STATIC_ROOT / path).resolve()
            if target.is_file() and target.is_relative_to(_STATIC_ROOT):
                return FileResponse(target)
        return FileResponse(_STATIC_ROOT / "index.html")
