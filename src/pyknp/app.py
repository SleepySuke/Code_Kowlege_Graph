'''
@Author ：suke
@Version ：1.1
@Date ：2026-06-16 01:56:00
@Description：FastAPI 应用工厂 — 装配 router + 静态资源 + 首页 HTML。
              store / uploads_root 通过 app.state 注入到路由处理器；
              启动时配置 logging（spec §6 要求 UNRESOLVED / 异常落到 logs）。
              uvicorn 入口：pyknp.app:app。
'''
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from pyknp.api.routes import router
from pyknp.storage.run_store import RunStore

FRONTEND_DIR = Path(__file__).parent / "frontend"
DEFAULT_DATA_DIR = Path("data")


def _configure_logging() -> None:
    """配置 root logger（spec §6 要求 UNRESOLVED / stage 异常写 log）。"""
    root = logging.getLogger("pyknp")
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        root.addHandler(handler)
        root.setLevel(logging.INFO)


def create_app(data_dir: Path | None = None) -> FastAPI:
    _configure_logging()

    data_dir = data_dir or DEFAULT_DATA_DIR
    data_dir.mkdir(parents=True, exist_ok=True)
    uploads_root = data_dir / "uploads"
    uploads_root.mkdir(parents=True, exist_ok=True)
    runs_root = data_dir / "runs"
    runs_root.mkdir(parents=True, exist_ok=True)

    store = RunStore(data_dir)

    app = FastAPI(title="pyknp · 知识图谱")
    app.state.store = store
    app.state.uploads_root = uploads_root

    app.include_router(router)

    if FRONTEND_DIR.exists():
        app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

        @app.get("/", response_class=HTMLResponse)
        async def index() -> str:
            return (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")

    return app


app = create_app()
