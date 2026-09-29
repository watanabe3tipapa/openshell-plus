from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from openshell_ui.core.config import Settings
from openshell_ui.main import create_app


def make_settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "demo": True,
        "host": "127.0.0.1",
        "workspace": "default",
        "sse_enabled": True,
    }
    base.update(overrides)
    return Settings(**base)


def make_client(**overrides: Any) -> TestClient:
    app: FastAPI = create_app(make_settings(**overrides))
    return TestClient(app)
