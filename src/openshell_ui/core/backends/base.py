from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field
from typing import Literal, Protocol

BackendKind = Literal["openshell", "demo"]
ExecStreamName = Literal["stdout", "stderr"]
ExecEventType = Literal["stdout", "stderr", "exit"]

PHASE_LABELS: dict[int, str] = {
    0: "unspecified",
    1: "provisioning",
    2: "ready",
    3: "error",
    4: "deleting",
    5: "unknown",
    6: "stopping",
    7: "stopped",
    8: "starting",
    9: "completed",
}


def phase_label(code: int) -> str:
    return PHASE_LABELS.get(code, "unknown")


@dataclass(slots=True)
class SandboxView:
    id: str
    name: str
    workspace: str
    phase: str
    phase_code: int = 0
    policy_version: int = 0
    exit_code: int | None = None
    labels: dict[str, str] = field(default_factory=dict)
    service_urls: dict[str, str] = field(default_factory=dict)
    created_from_template: str | None = None


@dataclass(slots=True)
class CreateRequest:
    name: str
    workspace: str
    labels: dict[str, str] = field(default_factory=dict)
    service_port: int | None = None
    service_name: str | None = None


@dataclass(slots=True)
class ExecRequest:
    command: list[str]
    workdir: str | None = None
    timeout_seconds: int | None = None


@dataclass(slots=True)
class ExecEvent:
    type: ExecEventType
    data: str = ""
    exit_code: int | None = None


class BackendError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


class BackendUnavailable(BackendError):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=503)


class SandboxBackend(Protocol):
    kind: BackendKind

    async def health(self) -> dict[str, object]: ...

    async def list(self, *, workspace: str | None = None) -> list[SandboxView]: ...

    async def get(self, name: str, *, workspace: str) -> SandboxView: ...

    async def create(self, request: CreateRequest) -> SandboxView: ...

    async def delete(self, name: str, *, workspace: str) -> None: ...

    def exec_stream(
        self, name: str, request: ExecRequest, *, workspace: str
    ) -> AsyncIterator[ExecEvent]: ...

    async def aclose(self) -> None: ...


def normalize_labels(labels: Mapping[str, str] | None) -> dict[str, str]:
    if not labels:
        return {}
    return {str(key): str(value) for key, value in labels.items() if str(key).strip()}
