from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from openshell_ui.core.config import Settings
from tests.helpers import make_client, make_settings

__all__ = ["make_client", "make_settings", "open_client", "secured_client"]


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """テストが開発者の .env やシェル環境変数に依存しないようにする。"""
    for key in list(os.environ):
        if key.startswith("OSUI_"):
            monkeypatch.delenv(key, raising=False)
    for key in ("VERCEL", "VERCEL_ENV", "OPENSHELL_SANDBOX_ID", "COLAB_RELEASE_TAG"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(
        "openshell_ui.core.config.Settings.model_config",
        {**Settings.model_config, "env_file": None},
        raising=False,
    )


@pytest.fixture
def open_client() -> Iterator[TestClient]:
    with make_client() as client:
        yield client


@pytest.fixture
def secured_client() -> Iterator[TestClient]:
    with make_client(auth_token="s3cret") as client:
        yield client
