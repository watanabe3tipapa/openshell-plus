from __future__ import annotations

import asyncio
import contextlib
import threading
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from openshell_ui.core.backends.base import (
    BackendError,
    BackendKind,
    BackendUnavailable,
    CreateRequest,
    ExecEvent,
    ExecRequest,
    SandboxView,
    normalize_labels,
    phase_label,
)
from openshell_ui.core.config import Settings, SettingsError, is_loopback_host


@dataclass(frozen=True, slots=True)
class Sdk:
    SandboxClient: Any
    SandboxError: type[BaseException]
    ServiceExposure: Any
    TlsConfig: Any
    ClientCredentialsAuth: Any
    ExecResult: Any
    ExecChunk: Any


_sdk_cache: Sdk | None = None


def load_sdk() -> Sdk:
    global _sdk_cache
    if _sdk_cache is not None:
        return _sdk_cache
    try:
        from openshell import (
            ClientCredentialsAuth,
            ExecChunk,
            ExecResult,
            SandboxClient,
            SandboxError,
            ServiceExposure,
            TlsConfig,
        )
    except ImportError as exc:
        raise BackendUnavailable(
            "the openshell SDK is not installed; run `uv sync --extra openshell`"
        ) from exc
    _sdk_cache = Sdk(
        SandboxClient=SandboxClient,
        SandboxError=SandboxError,
        ServiceExposure=ServiceExposure,
        TlsConfig=TlsConfig,
        ClientCredentialsAuth=ClientCredentialsAuth,
        ExecResult=ExecResult,
        ExecChunk=ExecChunk,
    )
    return _sdk_cache


def split_endpoint(raw: str) -> tuple[str, int]:
    candidate = raw.strip()
    if "//" not in candidate:
        candidate = f"//{candidate}"
    parsed = urlparse(candidate)
    host = parsed.hostname
    if not host:
        raise SettingsError(f"invalid gateway endpoint: {raw}")
    port = parsed.port
    if port is None:
        if parsed.scheme == "https":
            port = 443
        elif parsed.scheme == "http":
            port = 80
        else:
            raise SettingsError(
                "gateway endpoint must include a port, for example gw.example.com:17670"
            )
    return host, port


def _map_error(exc: BaseException) -> BackendError:
    try:
        sdk = load_sdk()
    except BackendUnavailable:
        sdk = None
    if sdk is not None and isinstance(exc, sdk.SandboxError):
        text = str(exc).lower()
        status = 502
        if "not found" in text:
            status = 404
        elif "already exists" in text:
            status = 409
        return BackendError(str(exc), status_code=status)
    code = getattr(exc, "code", None)
    if callable(code):
        try:
            name = str(getattr(code(), "name", ""))
        except Exception:
            name = ""
        if name in ("NOT_FOUND",):
            return BackendError(str(exc), status_code=404)
        if name in ("ALREADY_EXISTS", "FAILED_PRECONDITION"):
            return BackendError(str(exc), status_code=409)
        if name in ("UNAUTHENTICATED", "PERMISSION_DENIED"):
            return BackendError(str(exc), status_code=403)
        if name in ("UNAVAILABLE", "DEADLINE_EXCEEDED", "UNIMPLEMENTED"):
            return BackendError(str(exc), status_code=503)
    return BackendError(str(exc) or exc.__class__.__name__, status_code=502)


class OpenShellBackend:
    """Wraps the synchronous openshell SDK behind an async interface."""

    kind: BackendKind = "openshell"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: Any | None = None
        self._lock = threading.Lock()

    def _tls(self, sdk: Sdk) -> Any | None:
        settings = self._settings
        if not (settings.gateway_ca_cert or settings.gateway_cert or settings.gateway_key):
            return None
        return sdk.TlsConfig(
            ca_path=settings.gateway_ca_cert,
            cert_path=settings.gateway_cert,
            key_path=settings.gateway_key,
        )

    def _client_credentials(self, sdk: Sdk) -> Any | None:
        settings = self._settings
        if not settings.oidc_issuer:
            return None
        return sdk.ClientCredentialsAuth(
            issuer=settings.oidc_issuer,
            client_id=settings.oidc_client_id,
            client_secret=lambda: settings.oidc_client_secret or "",
            audience=settings.oidc_audience,
            scopes=tuple(settings.oidc_scopes),
            insecure=settings.gateway_insecure,
            timeout=settings.gateway_timeout,
        )

    def _build_client(self) -> Any:
        sdk = load_sdk()
        settings = self._settings
        credentials = self._client_credentials(sdk)
        if settings.gateway_endpoint:
            host, port = split_endpoint(settings.gateway_endpoint)
            tls = self._tls(sdk)
            if credentials is not None and tls is None and not is_loopback_host(host):
                raise SettingsError(
                    "OSUI_OIDC_* on a non-loopback gateway requires TLS; set "
                    "OSUI_GATEWAY_CA_CERT (and optionally CERT/KEY for mTLS)"
                )
            return sdk.SandboxClient(
                f"{host}:{port}",
                tls=tls,
                client_credentials=credentials,
                timeout=settings.gateway_timeout,
                cluster_name=settings.gateway_cluster,
            )
        return sdk.SandboxClient.from_active_cluster(
            cluster=settings.gateway_cluster,
            timeout=settings.gateway_timeout,
            insecure=settings.gateway_insecure,
            client_credentials=credentials,
        )

    def client(self) -> Any:
        if self._client is not None:
            return self._client
        with self._lock:
            if self._client is None:
                self._client = self._build_client()
            return self._client

    async def _call(self, func: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Any:
        try:
            return await asyncio.to_thread(func, *args, **kwargs)
        except SettingsError:
            raise
        except BaseException as exc:
            raise _map_error(exc) from exc

    def _to_view(self, ref: Any, workspace: str | None = None) -> SandboxView:
        status = ref.status
        template = getattr(ref, "created_from_workload_template", None)
        return SandboxView(
            id=ref.id,
            name=ref.name,
            workspace=getattr(ref, "workspace", None) or workspace or "",
            phase=phase_label(status.phase),
            phase_code=status.phase,
            policy_version=status.current_policy_version,
            exit_code=status.exit_code,
            labels=normalize_labels(getattr(ref, "labels", None)),
            service_urls=normalize_labels(getattr(ref, "service_urls", None)),
            created_from_template=getattr(template, "name", None) if template else None,
        )

    async def health(self) -> dict[str, object]:
        response = await self._call(self.client().health)
        return {
            "status": str(getattr(response, "status", "serving")),
            "version": str(getattr(response, "version", "")),
            "backend": "openshell",
            "detail": "connected to the configured OpenShell gateway",
        }

    async def list(self, *, workspace: str | None = None) -> list[SandboxView]:
        target = workspace or self._settings.workspace
        refs = await self._call(
            self.client().list_all,
            workspace=target,
            page_size=self._settings.page_size,
        )
        return [self._to_view(ref, target) for ref in refs]

    async def get(self, name: str, *, workspace: str) -> SandboxView:
        ref = await self._call(self.client().get, name, workspace=workspace)
        return self._to_view(ref, workspace)

    async def create(self, request: CreateRequest) -> SandboxView:
        sdk = load_sdk()
        exposures = None
        if request.service_port is not None:
            exposures = [
                sdk.ServiceExposure(
                    target_port=request.service_port, service=request.service_name or ""
                )
            ]
        ref = await self._call(
            self.client().create,
            workspace=request.workspace,
            name=request.name,
            labels=normalize_labels(request.labels) or None,
            service_exposures=exposures,
        )
        return self._to_view(ref, request.workspace)

    async def delete(self, name: str, *, workspace: str) -> None:
        await self._call(self.client().delete, name, workspace=workspace, allow_missing=False)

    async def exec_stream(
        self, name: str, request: ExecRequest, *, workspace: str
    ) -> AsyncIterator[ExecEvent]:
        sdk = load_sdk()
        client = self.client()
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[ExecEvent | BaseException | None] = asyncio.Queue()

        def emit(item: ExecEvent | BaseException | None) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, item)

        def worker() -> None:
            try:
                stream = client.exec_stream(
                    name,
                    request.command,
                    workspace=workspace,
                    workdir=request.workdir,
                    timeout_seconds=request.timeout_seconds,
                )
                for item in stream:
                    if isinstance(item, sdk.ExecResult):
                        emit(ExecEvent(type="exit", exit_code=item.exit_code))
                    else:
                        emit(
                            ExecEvent(
                                type=item.stream,
                                data=bytes(item.data).decode("utf-8", errors="replace"),
                            )
                        )
            except BaseException as exc:
                emit(exc)
            finally:
                emit(None)

        threading.Thread(target=worker, name=f"osui-exec-{name}", daemon=True).start()

        while True:
            item = await queue.get()
            if item is None:
                return
            if isinstance(item, BaseException):
                raise _map_error(item)
            yield item
            if item.type == "exit":
                return

    async def aclose(self) -> None:
        client, self._client = self._client, None
        if client is None:
            return
        with contextlib.suppress(BaseException):
            await asyncio.to_thread(client.close)
