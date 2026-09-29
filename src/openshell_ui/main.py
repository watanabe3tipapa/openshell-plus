from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from openshell_ui import __version__
from openshell_ui.api import exec as exec_api
from openshell_ui.api import meta, sandboxes
from openshell_ui.core.backends.base import BackendError
from openshell_ui.core.config import Settings, SettingsError, get_settings
from openshell_ui.core.factory import create_backend
from openshell_ui.core.mode import RunMode, detect_mode

UI_DIR = Path(__file__).resolve().parent / "ui"

logger = logging.getLogger("openshell_ui")


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    settings.validate_startup()
    mode: RunMode = detect_mode(settings.mode)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        backend, source = await create_backend(settings)
        app.state.backend = backend
        app.state.backend_source = source
        logger.info(
            "run_mode=%s backend=%s (%s) auth=%s",
            mode,
            backend.kind,
            source,
            "token" if settings.auth_required else "open",
        )
        try:
            yield
        finally:
            await backend.aclose()

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description=(
            "UI/UX layer for NVIDIA OpenShell. Works against a local gateway, "
            "a remote gateway, or an in-memory demo backend."
        ),
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.mode = mode

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.exception_handler(BackendError)
    async def handle_backend_error(request: Request, exc: BackendError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})

    @app.exception_handler(SettingsError)
    async def handle_settings_error(request: Request, exc: SettingsError) -> JSONResponse:
        return JSONResponse(status_code=500, content={"detail": str(exc)})

    app.include_router(meta.router, prefix="/api")
    app.include_router(sandboxes.router, prefix="/api")
    app.include_router(exec_api.router, prefix="/api")

    app.mount("/assets", StaticFiles(directory=UI_DIR / "assets"), name="assets")

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(UI_DIR / "index.html", headers={"Cache-Control": "no-store"})

    @app.get("/favicon.svg", include_in_schema=False)
    async def favicon() -> FileResponse:
        return FileResponse(UI_DIR / "assets" / "favicon.svg")

    return app


def main() -> None:
    import uvicorn

    settings = get_settings()
    configure_logging(settings.log_level)
    uvicorn.run(
        "openshell_ui.main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        reload=settings.debug,
    )


app = create_app()


if __name__ == "__main__":
    main()
