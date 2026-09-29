from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from openshell_ui.api.auth import require_auth, token_from_subprotocol, token_matches
from openshell_ui.core.backends.base import BackendError, ExecEvent, ExecRequest
from openshell_ui.core.config import Settings

router = APIRouter(tags=["exec"])

WS_CLOSE_UNAUTHORIZED = 4401


class ExecPayload(BaseModel):
    """exec の入力。SDK が対応していない env などを黙って捨てないよう extra を拒否する。"""

    model_config = ConfigDict(extra="forbid")

    command: list[str] = Field(min_length=1)
    workdir: str | None = None
    timeout_seconds: int | None = Field(default=None, ge=1)


def _build_request(settings: Settings, payload: ExecPayload) -> ExecRequest:
    timeout = payload.timeout_seconds or settings.exec_default_timeout
    return ExecRequest(
        command=payload.command,
        workdir=payload.workdir,
        timeout_seconds=min(timeout, settings.exec_max_timeout),
    )


def _serialize(event: ExecEvent) -> dict[str, object]:
    return {"type": event.type, "data": event.data, "exit_code": event.exit_code}


def _serialize_error(exc: BackendError) -> dict[str, object]:
    return {
        "type": "error",
        "detail": str(exc),
        "status_code": exc.status_code,
        "data": "",
        "exit_code": None,
    }


@router.post(
    "/sandboxes/{name}/exec",
    dependencies=[Depends(require_auth)],
    summary="Run a command and return the aggregated result",
)
async def run_command(name: str, payload: ExecPayload, request: Request) -> dict[str, object]:
    settings: Settings = request.app.state.settings
    stdout: list[str] = []
    stderr: list[str] = []
    exit_code = 0
    exec_request = _build_request(settings, payload)
    async for event in request.app.state.backend.exec_stream(
        name, exec_request, workspace=settings.workspace
    ):
        if event.type == "stdout":
            stdout.append(event.data)
        elif event.type == "stderr":
            stderr.append(event.data)
        else:
            exit_code = event.exit_code if event.exit_code is not None else 0
    return {
        "sandbox": name,
        "workspace": settings.workspace,
        "command": payload.command,
        "exit_code": exit_code,
        "stdout": "".join(stdout),
        "stderr": "".join(stderr),
    }


@router.get(
    "/sandboxes/{name}/exec/stream",
    dependencies=[Depends(require_auth)],
    summary="Server-Sent Events variant of the exec stream",
)
async def stream_command_sse(
    name: str,
    request: Request,
    command: Annotated[list[str], Query(min_length=1)],
    workdir: str | None = None,
    timeout_seconds: Annotated[int | None, Query(ge=1)] = None,
) -> StreamingResponse:
    settings: Settings = request.app.state.settings
    if not settings.sse_enabled:
        raise HTTPException(
            status_code=404,
            detail=(
                "SSE is disabled; Cloudflare Quick Tunnels do not support it, "
                "use the WebSocket endpoint"
            ),
        )
    payload = ExecPayload(command=command, workdir=workdir, timeout_seconds=timeout_seconds)
    exec_request = _build_request(settings, payload)
    backend = request.app.state.backend

    async def events() -> AsyncIterator[str]:
        try:
            async for event in backend.exec_stream(
                name, exec_request, workspace=settings.workspace
            ):
                yield f"data: {json.dumps(_serialize(event), ensure_ascii=False)}\n\n"
        except BackendError as exc:
            yield f"data: {json.dumps(_serialize_error(exc), ensure_ascii=False)}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@router.websocket("/sandboxes/{name}/exec")
async def stream_command_ws(websocket: WebSocket, name: str) -> None:
    settings: Settings = websocket.app.state.settings
    subprotocol = token_from_subprotocol(websocket.headers.get("sec-websocket-protocol"))
    offered = [
        part.strip()
        for part in (websocket.headers.get("sec-websocket-protocol") or "").split(",")
        if part.strip()
    ]
    provided = subprotocol or websocket.query_params.get("token")
    if not token_matches(settings, provided):
        await websocket.close(code=WS_CLOSE_UNAUTHORIZED)
        return
    accept_protocol = offered[0] if subprotocol and offered else None
    await websocket.accept(subprotocol=accept_protocol)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                payload = ExecPayload.model_validate_json(raw)
            except ValidationError as exc:
                await websocket.send_json(
                    {"type": "error", "detail": f"invalid payload: {exc.error_count()} error(s)"}
                )
                continue
            exec_request = _build_request(settings, payload)
            try:
                async for event in websocket.app.state.backend.exec_stream(
                    name, exec_request, workspace=settings.workspace
                ):
                    await websocket.send_json(_serialize(event))
            except BackendError as exc:
                await websocket.send_json(_serialize_error(exc))
    except WebSocketDisconnect:
        return
