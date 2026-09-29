from __future__ import annotations

import json

from fastapi.testclient import TestClient

from tests.helpers import make_client


def create(client: TestClient, name: str = "box") -> None:
    assert client.post("/api/sandboxes", json={"name": name}).status_code == 201


def test_post_exec_aggregates_stdout(open_client: TestClient) -> None:
    create(open_client)
    response = open_client.post("/api/sandboxes/box/exec", json={"command": ["echo", "hi"]})
    assert response.status_code == 200
    body = response.json()
    assert body["exit_code"] == 0
    assert body["stdout"].startswith("$ echo hi\n")
    assert "hi" in body["stdout"]
    assert body["stderr"] == ""
    assert body["workspace"] == "default"


def test_post_exec_known_commands(open_client: TestClient) -> None:
    create(open_client)
    for command, needle in (
        (["pwd"], "/workspace"),
        (["ls"], "pyproject.toml"),
        (["whoami"], "sandbox"),
    ):
        body = open_client.post("/api/sandboxes/box/exec", json={"command": command}).json()
        assert needle in body["stdout"], command


def test_post_exec_unknown_sandbox_returns_404(open_client: TestClient) -> None:
    response = open_client.post("/api/sandboxes/ghost/exec", json={"command": ["ls"]})
    assert response.status_code == 404


def test_post_exec_rejects_empty_command(open_client: TestClient) -> None:
    create(open_client)
    response = open_client.post("/api/sandboxes/box/exec", json={"command": []})
    assert response.status_code == 422


def test_post_exec_rejects_unknown_field(open_client: TestClient) -> None:
    """Env は未実装のため、payload に env を含めると拒否されること。"""
    create(open_client)
    response = open_client.post(
        "/api/sandboxes/box/exec", json={"command": ["ls"], "env": {"A": "B"}}
    )
    assert response.status_code == 422


def test_post_exec_rejects_zero_timeout(open_client: TestClient) -> None:
    create(open_client)
    response = open_client.post(
        "/api/sandboxes/box/exec", json={"command": ["ls"], "timeout_seconds": 0}
    )
    assert response.status_code == 422


def test_timeout_is_clamped_to_max() -> None:
    with make_client(exec_max_timeout=5, exec_default_timeout=1) as client:
        create(client)
        body = client.post(
            "/api/sandboxes/box/exec",
            json={"command": ["ls"], "timeout_seconds": 9999},
        )
        assert body.status_code == 200


def test_sse_stream_emits_events(open_client: TestClient) -> None:
    create(open_client)
    with open_client.stream(
        "GET", "/api/sandboxes/box/exec/stream", params={"command": "echo"}
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert response.headers["cache-control"] == "no-store"
        payload = "".join(response.iter_text())

    events = [
        json.loads(line.removeprefix("data: "))
        for line in payload.splitlines()
        if line.startswith("data: ")
    ]
    assert [event["type"] for event in events] == ["stdout", "stdout", "exit"]
    assert events[-1]["exit_code"] == 0


def test_sse_reports_backend_error_as_event(open_client: TestClient) -> None:
    with open_client.stream(
        "GET", "/api/sandboxes/ghost/exec/stream", params={"command": "echo"}
    ) as response:
        payload = "".join(response.iter_text())
    event = json.loads(payload.removeprefix("data: ").strip())
    assert event["type"] == "error"
    assert event["status_code"] == 404


def test_sse_returns_404_when_disabled() -> None:
    with make_client(sse_enabled=False) as client:
        create(client)
        response = client.get("/api/sandboxes/box/exec/stream", params={"command": "echo"})
        assert response.status_code == 404
        assert "Quick Tunnels" in response.json()["detail"]


def test_websocket_streams_exec_events(open_client: TestClient) -> None:
    create(open_client)
    with open_client.websocket_connect("/api/sandboxes/box/exec") as socket:
        socket.send_text(json.dumps({"command": ["echo", "ws"]}))
        events = [socket.receive_json() for _ in range(3)]
    assert [event["type"] for event in events] == ["stdout", "stdout", "exit"]
    assert "ws" in events[1]["data"]


def test_websocket_reports_invalid_payload_and_continues(open_client: TestClient) -> None:
    create(open_client)
    with open_client.websocket_connect("/api/sandboxes/box/exec") as socket:
        socket.send_text(json.dumps({"command": []}))
        error = socket.receive_json()
        assert error["type"] == "error"
        assert "invalid payload" in error["detail"]

        socket.send_text(json.dumps({"command": ["pwd"]}))
        events = [socket.receive_json() for _ in range(3)]
    assert events[-1]["type"] == "exit"


def test_websocket_backend_error_is_reported(open_client: TestClient) -> None:
    with open_client.websocket_connect("/api/sandboxes/ghost/exec") as socket:
        socket.send_text(json.dumps({"command": ["ls"]}))
        event = socket.receive_json()
    assert event["type"] == "error"
    assert event["status_code"] == 404
