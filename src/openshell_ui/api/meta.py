from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from openshell_ui import __version__
from openshell_ui.api.auth import require_auth
from openshell_ui.core.backends.base import BackendError
from openshell_ui.core.config import Settings

router = APIRouter()


@router.get("/health", summary="Liveness and backend reachability")
async def health(request: Request) -> dict[str, object]:
    settings: Settings = request.app.state.settings
    backend = request.app.state.backend
    payload: dict[str, object] = {
        "app": settings.app_name,
        "version": __version__,
        "run_mode": str(request.app.state.mode),
        "backend": backend.kind,
        "backend_source": request.app.state.backend_source,
        "auth_required": settings.auth_required,
    }
    try:
        payload["gateway"] = await backend.health()
        payload["ok"] = True
    except BackendError as exc:
        payload["gateway"] = {"status": "unavailable", "detail": str(exc)}
        payload["ok"] = False
    return payload


@router.get("/config", dependencies=[Depends(require_auth)], summary="UI capabilities")
async def read_config(request: Request) -> dict[str, object]:
    settings: Settings = request.app.state.settings
    return {
        "app": settings.app_name,
        "version": __version__,
        "run_mode": str(request.app.state.mode),
        "backend": request.app.state.backend.kind,
        "backend_source": request.app.state.backend_source,
        "workspace": settings.workspace,
        "auth_required": settings.auth_required,
        "public_bind": settings.public_bind,
        "capabilities": {
            "websocket": True,
            "sse": settings.sse_enabled,
            "demo": request.app.state.backend.kind == "demo",
        },
    }
