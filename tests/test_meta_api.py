from __future__ import annotations

import json
import re

from fastapi.testclient import TestClient

from tests.helpers import make_client


def test_health_is_public(open_client: TestClient) -> None:
    body = open_client.get("/api/health").json()
    assert body["ok"] is True
    assert body["backend"] == "demo"
    assert body["run_mode"] == "local"
    assert body["auth_required"] is False
    assert body["gateway"]["status"] == "serving"


def test_version_comes_from_package_metadata(open_client: TestClient) -> None:
    """バージョンは __version__ だけが情報源で、Settings と二重管理しない。"""
    from importlib.metadata import version as dist_version

    from openshell_ui import __version__

    assert open_client.get("/api/health").json()["version"] == __version__
    assert open_client.get("/api/config").json()["version"] == __version__
    assert dist_version("openshell-ui") == __version__


def test_version_is_a_plain_release_number() -> None:
    """リリースとして切り出すため、dev suffix のない数字 3 段であることを確認する。"""
    from openshell_ui import __version__

    assert re.fullmatch(r"\d+\.\d+\.\d+", __version__)


def test_config_reports_capabilities(open_client: TestClient) -> None:
    body = open_client.get("/api/config").json()
    assert body["workspace"] == "default"
    assert body["public_bind"] is False
    assert body["capabilities"] == {"websocket": True, "sse": True, "demo": True}


def test_config_hides_sse_when_disabled() -> None:
    with make_client(sse_enabled=False) as client:
        body = client.get("/api/config").json()
        assert body["capabilities"]["sse"] is False


def test_index_and_static_assets_are_served(open_client: TestClient) -> None:
    index = open_client.get("/")
    assert index.status_code == 200
    assert "text/html" in index.headers["content-type"]

    favicon = open_client.get("/favicon.svg")
    assert favicon.status_code == 200
    assert "image/svg+xml" in favicon.headers["content-type"]


def test_openapi_schema_is_generated(open_client: TestClient) -> None:
    schema = open_client.get("/openapi.json")
    assert schema.status_code == 200
    paths = schema.json()["paths"]
    assert "/api/sandboxes" in paths
    assert "/api/sandboxes/{name}/exec" in paths


def test_json_body_is_utf8_safe(open_client: TestClient) -> None:
    response = open_client.post(
        "/api/sandboxes", json={"name": "utf8", "labels": {"メモ": "日本語"}}
    )
    assert response.status_code == 201
    assert response.json()["labels"] == {"メモ": "日本語"}
    assert "日本語" in response.text
    assert json.dumps(response.json(), ensure_ascii=False)
