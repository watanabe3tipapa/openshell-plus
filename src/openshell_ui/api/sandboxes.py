from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from openshell_ui.api.auth import require_auth
from openshell_ui.core.backends.base import CreateRequest, SandboxView

router = APIRouter(dependencies=[Depends(require_auth)], tags=["sandboxes"])


class SandboxCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        min_length=1,
        max_length=63,
        pattern=r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$",
        description="DNS-1123 label, used as the sandbox name key",
    )
    workspace: str | None = None
    labels: dict[str, str] = Field(default_factory=dict)
    service_port: int | None = Field(default=None, ge=1, le=65535)
    service_name: str | None = None


def _workspace(request: Request, override: str | None = None) -> str:
    settings = request.app.state.settings
    return override or settings.workspace


@router.get("/sandboxes", response_model=list[SandboxView])
async def list_sandboxes(request: Request, workspace: str | None = None) -> list[SandboxView]:
    target = _workspace(request, workspace)
    return await request.app.state.backend.list(workspace=target)


@router.post("/sandboxes", response_model=SandboxView, status_code=201)
async def create_sandbox(payload: SandboxCreate, request: Request) -> SandboxView:
    target = _workspace(request, payload.workspace)
    return await request.app.state.backend.create(
        CreateRequest(
            name=payload.name,
            workspace=target,
            labels=payload.labels,
            service_port=payload.service_port,
            service_name=payload.service_name,
        )
    )


@router.get("/sandboxes/{name}", response_model=SandboxView)
async def get_sandbox(name: str, request: Request, workspace: str | None = None) -> SandboxView:
    target = _workspace(request, workspace)
    return await request.app.state.backend.get(name, workspace=target)


@router.delete("/sandboxes/{name}")
async def delete_sandbox(name: str, request: Request, workspace: str | None = None) -> dict:
    target = _workspace(request, workspace)
    await request.app.state.backend.delete(name, workspace=target)
    return {"deleted": name, "workspace": target}


@router.get("/sandboxes/{name}/service-urls")
async def service_urls(
    name: str, request: Request, workspace: str | None = None
) -> dict[str, object]:
    target = _workspace(request, workspace)
    view = await request.app.state.backend.get(name, workspace=target)
    return {"sandbox": view.name, "service_urls": view.service_urls}
