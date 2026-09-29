from __future__ import annotations

import asyncio
import itertools
import time
from collections.abc import AsyncIterator

from openshell_ui.core.backends.base import (
    BackendError,
    BackendKind,
    CreateRequest,
    ExecEvent,
    ExecRequest,
    SandboxView,
)

_PROVISIONING_SECONDS = 0.8


class DemoBackend:
    """In-memory backend used whenever no OpenShell gateway is reachable."""

    kind: BackendKind = "demo"

    def __init__(self, *, latency: float = 0.04) -> None:
        self._latency = latency
        self._items: dict[tuple[str, str], SandboxView] = {}
        self._created: dict[tuple[str, str], float] = {}
        self._counter = itertools.count(1)

    def _current(self, key: tuple[str, str]) -> SandboxView:
        view = self._items[key]
        if view.phase == "provisioning" and (
            time.monotonic() - self._created[key] >= _PROVISIONING_SECONDS
        ):
            view.phase = "ready"
            view.phase_code = 2
        return view

    async def health(self) -> dict[str, object]:
        return {
            "status": "serving",
            "version": "demo",
            "backend": "demo",
            "detail": "in-memory sandboxes, no OpenShell gateway attached",
        }

    async def list(self, *, workspace: str | None = None) -> list[SandboxView]:
        await asyncio.sleep(0)
        return [
            self._current(key) for key in self._items if workspace is None or key[0] == workspace
        ]

    async def get(self, name: str, *, workspace: str) -> SandboxView:
        await asyncio.sleep(0)
        key = (workspace, name)
        if key not in self._items:
            raise BackendError(f"sandbox not found: {name}", status_code=404)
        return self._current(key)

    async def create(self, request: CreateRequest) -> SandboxView:
        await asyncio.sleep(0)
        key = (request.workspace, request.name)
        if key in self._items:
            raise BackendError(f"sandbox already exists: {request.name}", status_code=409)
        view = SandboxView(
            id=f"demo-{next(self._counter):04d}",
            name=request.name,
            workspace=request.workspace,
            phase="provisioning",
            phase_code=1,
            labels=dict(request.labels),
        )
        self._items[key] = view
        self._created[key] = time.monotonic()
        return view

    async def delete(self, name: str, *, workspace: str) -> None:
        await asyncio.sleep(0)
        key = (workspace, name)
        if key not in self._items:
            raise BackendError(f"sandbox not found: {name}", status_code=404)
        del self._items[key]
        self._created.pop(key, None)

    async def exec_stream(
        self, name: str, request: ExecRequest, *, workspace: str
    ) -> AsyncIterator[ExecEvent]:
        key = (workspace, name)
        if key not in self._items:
            raise BackendError(f"sandbox not found: {name}", status_code=404)
        command = " ".join(request.command)
        yield ExecEvent(type="stdout", data=f"$ {command}\n")
        for line in self._script(request.command):
            await asyncio.sleep(self._latency)
            yield ExecEvent(type="stdout", data=f"{line}\n")
        yield ExecEvent(type="exit", exit_code=0)

    def _script(self, command: list[str]) -> list[str]:
        head = command[0] if command else ""
        if head in ("ls", "dir"):
            return ["app", "pyproject.toml", "src", "uv.lock"]
        if head == "pwd":
            return ["/workspace"]
        if head in ("whoami", "hostname"):
            return ["sandbox"]
        if head in ("uname", "python", "python3", "node", "uv"):
            return [f"demo {head} output (no real sandbox is attached)"]
        if head in ("echo",):
            return [" ".join(command[1:])]
        return [f"demo: executed {head!r} without a real sandbox"]

    async def aclose(self) -> None:
        return None
