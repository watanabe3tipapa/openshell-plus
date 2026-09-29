from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def create(client: TestClient, name: str = "box", **extra: object) -> dict:
    response = client.post("/api/sandboxes", json={"name": name, **extra})
    assert response.status_code == 201, response.text
    return response.json()


def test_create_returns_provisioning_phase(open_client: TestClient) -> None:
    body = create(open_client, "box-1")
    assert body["name"] == "box-1"
    assert body["workspace"] == "default"
    assert body["phase"] == "provisioning"
    assert body["phase_code"] == 1
    assert body["id"].startswith("demo-")


def test_create_accepts_labels(open_client: TestClient) -> None:
    body = create(open_client, "box-2", labels={"env": "test"})
    assert body["labels"] == {"env": "test"}


def test_create_honours_workspace_override(open_client: TestClient) -> None:
    body = create(open_client, "box-3", workspace="team-a")
    assert body["workspace"] == "team-a"


def test_create_is_scoped_per_workspace(open_client: TestClient) -> None:
    create(open_client, "shared", workspace="team-a")
    create(open_client, "shared", workspace="team-b")

    a = open_client.get("/api/sandboxes", params={"workspace": "team-a"}).json()
    b = open_client.get("/api/sandboxes", params={"workspace": "team-b"}).json()
    assert [item["workspace"] for item in a] == ["team-a"]
    assert [item["workspace"] for item in b] == ["team-b"]


def test_duplicate_name_returns_409(open_client: TestClient) -> None:
    create(open_client, "dup")
    response = open_client.post("/api/sandboxes", json={"name": "dup"})
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


def test_list_returns_created_items(open_client: TestClient) -> None:
    create(open_client, "a")
    create(open_client, "b")
    names = {item["name"] for item in open_client.get("/api/sandboxes").json()}
    assert names == {"a", "b"}


def test_get_returns_item(open_client: TestClient) -> None:
    create(open_client, "one")
    body = open_client.get("/api/sandboxes/one").json()
    assert body["name"] == "one"


def test_get_unknown_returns_404(open_client: TestClient) -> None:
    response = open_client.get("/api/sandboxes/missing")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_get_in_other_workspace_returns_404(open_client: TestClient) -> None:
    create(open_client, "scoped", workspace="team-a")
    response = open_client.get("/api/sandboxes/scoped", params={"workspace": "team-b"})
    assert response.status_code == 404


def test_delete_removes_item(open_client: TestClient) -> None:
    create(open_client, "gone")
    response = open_client.delete("/api/sandboxes/gone")
    assert response.status_code == 200
    assert response.json() == {"deleted": "gone", "workspace": "default"}
    assert open_client.get("/api/sandboxes/gone").status_code == 404


def test_delete_unknown_returns_404(open_client: TestClient) -> None:
    assert open_client.delete("/api/sandboxes/missing").status_code == 404


def test_service_urls_endpoint_exists(open_client: TestClient) -> None:
    create(open_client, "svc", service_port=8000, service_name="web")
    body = open_client.get("/api/sandboxes/svc/service-urls").json()
    assert body["sandbox"] == "svc"
    assert "service_urls" in body


@pytest.mark.parametrize(
    "name",
    [
        "UPPER",
        "-leading",
        "trailing-",
        "with space",
        "",
        "under_score",
        "a" * 64,
        "日本語",
    ],
)
def test_invalid_names_are_rejected(open_client: TestClient, name: str) -> None:
    response = open_client.post("/api/sandboxes", json={"name": name})
    assert response.status_code == 422, response.text


def test_service_port_range_is_validated(open_client: TestClient) -> None:
    assert (
        open_client.post("/api/sandboxes", json={"name": "p1", "service_port": 0}).status_code
        == 422
    )
    assert (
        open_client.post("/api/sandboxes", json={"name": "p2", "service_port": 70000}).status_code
        == 422
    )
