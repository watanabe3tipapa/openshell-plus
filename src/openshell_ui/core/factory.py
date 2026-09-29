from __future__ import annotations

import logging

from openshell_ui.core.backends.base import BackendError, SandboxBackend
from openshell_ui.core.backends.demo import DemoBackend
from openshell_ui.core.backends.openshell_backend import OpenShellBackend
from openshell_ui.core.config import Settings

logger = logging.getLogger(__name__)


async def create_backend(settings: Settings) -> tuple[SandboxBackend, str]:
    if settings.demo:
        return DemoBackend(), "demo forced by OSUI_DEMO"

    backend = OpenShellBackend(settings)
    try:
        await backend.health()
    except Exception as exc:
        await backend.aclose()
        if settings.require_gateway:
            raise BackendError(
                f"OSUI_REQUIRE_GATEWAY is set but the OpenShell gateway is unreachable: {exc}",
                status_code=503,
            ) from exc
        logger.warning("OpenShell gateway unreachable, falling back to the demo backend: %s", exc)
        return DemoBackend(), f"demo fallback ({exc})"
    return backend, "OpenShell gateway"
