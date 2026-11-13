"""FastAPI application: REST API + conversation WebSocket + built frontend (SPA)."""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.api.routes import live
from app.core.config import BACKEND_DIR, get_settings
from app.core.logging import setup_logging
from app.db.session import SessionLocal, engine
from app.seed.topics import seed_topics
from app.services import access, tasks
from app.services.lessons import fail_stale_jobs
from app.services.speech import tts

log = logging.getLogger("app")


def run_migrations() -> None:
    from alembic.config import Config

    from alembic import command

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.attributes["configure_logger"] = False  # keep the app's logging config
    command.upgrade(cfg, "head")


@asynccontextmanager
async def lifespan(_: FastAPI):
    setup_logging()
    if get_settings().run_migrations_on_startup:
        await asyncio.to_thread(run_migrations)
    async with SessionLocal() as session:
        await seed_topics(session)
        await fail_stale_jobs(session)
    tasks.spawn(tts.warm_up(), name="tts-warmup")
    maintenance = asyncio.create_task(tts.cache_maintenance(), name="tts-cache-maintenance")
    yield
    maintenance.cancel()
    await tasks.wait_all(grace_seconds=10)
    await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    docs = settings.api_docs
    app = FastAPI(
        title="AI English Tutor",
        version="0.2.0",
        lifespan=lifespan,
        docs_url="/docs" if docs else None,
        redoc_url=None,
        openapi_url="/openapi.json" if docs else None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_exception_handler(access.AccessError, _access_denied)
    app.include_router(api_router)
    app.include_router(live.router)
    _mount_frontend(app, settings.frontend_dist)
    return app


async def _access_denied(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, access.AccessError)
    return JSONResponse({"detail": str(exc)}, status_code=exc.status)


def _mount_frontend(app: FastAPI, dist: Path) -> None:
    """Serve the built React app; unknown non-API paths fall back to index.html (client-side routing)."""
    index = dist / "index.html"
    if not index.exists():
        log.warning("Frontend build not found at %s — run `npm run build` in frontend/ (or use Vite dev)", dist)
        return
    root = dist.resolve()
    files = {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()}  # whitelist of servable files
    if (dist / "assets").exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str) -> FileResponse:
        if path.startswith(("api/", "ws/")):
            raise HTTPException(404)
        if path in files:
            return FileResponse(root / path)
        return FileResponse(index)


app = create_app()
