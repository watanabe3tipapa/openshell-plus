from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from openshell_ui.api.auth import extract_token, token_from_subprotocol, token_matches
from tests.helpers import make_client, make_settings

TOKEN = "s3cret"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def test_token_from_subprotocol_picks_bearer_entry() -> None:
    assert token_from_subprotocol("bearer.abc") == "abc"
    assert token_from_subprotocol("bearer.abc, chat") == "abc"
    assert token_from_subprotocol("chat, Bearer.abc") == "abc"


def test_token_from_subprotocol_ignores_other_protocols() -> None:
    assert token_from_subprotocol("chat") is None
    assert token_from_subprotocol("chat, superchat") is None
    assert token_from_subprotocol("bearer.") is None
    assert token_from_subprotocol("") is None
    assert token_from_subprotocol(None) is None


def test_extract_token_prefers_header() -> None:
    class FakeRequest:
        headers = {
            "authorization": "Bearer header-token",
            "sec-websocket-protocol": "bearer.sub-token",
        }
        query_params: dict[str, str] = {"token": "query-token"}

    assert extract_token(FakeRequest()) == "header-token"  # type: ignore[arg-type]


def test_token_matches_open_mode() -> None:
    assert token_matches(make_settings(), None) is True


def test_token_matches_secure_mode() -> None:
    settings = make_settings(auth_token=TOKEN)
    assert token_matches(settings, TOKEN) is True
    assert token_matches(settings, "wrong") is False
    assert token_matches(settings, None) is False


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/config"),
        ("GET", "/api/sandboxes"),
        ("POST", "/api/sandboxes"),
        ("GET", "/api/sandboxes/x"),
        ("DELETE", "/api/sandboxes/x"),
        ("POST", "/api/sandboxes/x/exec"),
        ("GET", "/api/sandboxes/x/exec/stream?command=ls"),
    ],
)
def test_protected_endpoints_require_token(
    secured_client: TestClient, method: str, path: str
) -> None:
    response = secured_client.request(method, path, json={"name": "x"})
    assert response.status_code == 401, path
    assert response.headers.get("WWW-Authenticate") == "Bearer"


def test_health_stays_public_when_secured(secured_client: TestClient) -> None:
    assert secured_client.get("/api/health").status_code == 200


def test_token_allows_access(secured_client: TestClient) -> None:
    assert secured_client.get("/api/config", headers=AUTH).status_code == 200
    created = secured_client.post("/api/sandboxes", json={"name": "x"}, headers=AUTH)
    assert created.status_code == 201
    assert secured_client.get("/api/sandboxes", headers=AUTH).status_code == 200


def test_wrong_token_is_rejected(secured_client: TestClient) -> None:
    response = secured_client.get("/api/sandboxes", headers={"Authorization": "Bearer nope"})
    assert response.status_code == 401


def test_query_token_is_accepted_for_sse(secured_client: TestClient) -> None:
    assert (
        secured_client.post("/api/sandboxes", json={"name": "q"}, headers=AUTH).status_code == 201
    )
    with secured_client.stream(
        "GET", f"/api/sandboxes/q/exec/stream?command=ls&token={TOKEN}"
    ) as response:
        assert response.status_code == 200


def test_websocket_accepts_subprotocol_token(secured_client: TestClient) -> None:
    assert (
        secured_client.post("/api/sandboxes", json={"name": "w"}, headers=AUTH).status_code == 201
    )
    with secured_client.websocket_connect(
        "/api/sandboxes/w/exec", subprotocols=[f"bearer.{TOKEN}"]
    ) as socket:
        socket.send_text('{"command": ["ls"]}')
        assert socket.receive_json()["type"] == "stdout"


def test_websocket_without_token_closes_with_4401(secured_client: TestClient) -> None:
    with (
        pytest.raises(WebSocketDisconnect) as excinfo,
        secured_client.websocket_connect("/api/sandboxes/w/exec") as socket,
    ):
        socket.receive_json()
    assert excinfo.value.code == 4401


def test_websocket_with_wrong_token_closes_with_4401(secured_client: TestClient) -> None:
    with (
        pytest.raises(WebSocketDisconnect) as excinfo,
        secured_client.websocket_connect(
            "/api/sandboxes/w/exec", subprotocols=["bearer.wrong"]
        ) as socket,
    ):
        socket.receive_json()
    assert excinfo.value.code == 4401


def test_cors_headers_are_sent_for_configured_origin() -> None:
    with make_client(auth_token=TOKEN, cors_origins=["https://example.com"]) as client:
        response = client.get("/api/config", headers={**AUTH, "Origin": "https://example.com"})
        assert response.headers["access-control-allow-origin"] == "https://example.com"
