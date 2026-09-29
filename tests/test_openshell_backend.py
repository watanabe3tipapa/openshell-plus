from __future__ import annotations

import asyncio
import dataclasses
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from openshell_ui.core.backends import openshell_backend as mod
from openshell_ui.core.backends.base import (
    BackendError,
    BackendUnavailable,
    CreateRequest,
    ExecRequest,
    SandboxView,
)
from openshell_ui.core.config import SettingsError
from tests.helpers import make_settings


def stub_sdk() -> mod.Sdk:
    return mod.Sdk(
        SandboxClient=MagicMock(name="SandboxClient"),
        SandboxError=RuntimeError,
        ServiceExposure=MagicMock(name="ServiceExposure"),
        TlsConfig=MagicMock(name="TlsConfig"),
        ClientCredentialsAuth=MagicMock(name="ClientCredentialsAuth"),
        ExecResult=MagicMock(name="ExecResult"),
        ExecChunk=MagicMock(name="ExecChunk"),
    )


def with_exec_result(sdk: mod.Sdk) -> mod.Sdk:
    return dataclasses.replace(sdk, ExecResult=FakeExecResult)


@pytest.fixture
def sdk(monkeypatch: pytest.MonkeyPatch) -> mod.Sdk:
    value = stub_sdk()
    monkeypatch.setattr(mod, "load_sdk", lambda: value)
    return value


def backend(**overrides: object) -> mod.OpenShellBackend:
    return mod.OpenShellBackend(make_settings(demo=False, **overrides))  # type: ignore[arg-type]


# ---------------------------------------------------------------- split_endpoint


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("gw.example.com:17670", ("gw.example.com", 17670)),
        ("https://gw.example.com:8443", ("gw.example.com", 8443)),
        ("http://127.0.0.1:18080", ("127.0.0.1", 18080)),
        ("https://gw.example.com", ("gw.example.com", 443)),
        ("http://gw.example.com", ("gw.example.com", 80)),
        ("  gw.example.com:17670  ", ("gw.example.com", 17670)),
    ],
)
def test_split_endpoint(raw: str, expected: tuple[str, int]) -> None:
    assert mod.split_endpoint(raw) == expected


@pytest.mark.parametrize("raw", ["gw.example.com", "localhost", "unix:/tmp/sock"])
def test_split_endpoint_requires_port(raw: str) -> None:
    with pytest.raises(SettingsError, match="must include a port|invalid gateway endpoint"):
        mod.split_endpoint(raw)


def test_split_endpoint_rejects_hostless_url() -> None:
    with pytest.raises(SettingsError, match="invalid gateway endpoint"):
        mod.split_endpoint("https://")


# -------------------------------------------------------------------- _map_error


class CodedError(Exception):
    def __init__(self, name: str) -> None:
        super().__init__(f"code {name}")
        self._name = name

    def code(self) -> SimpleNamespace:
        return SimpleNamespace(name=self._name)


@pytest.mark.parametrize(
    ("name", "status"),
    [
        ("NOT_FOUND", 404),
        ("ALREADY_EXISTS", 409),
        ("FAILED_PRECONDITION", 409),
        ("UNAUTHENTICATED", 403),
        ("PERMISSION_DENIED", 403),
        ("UNAVAILABLE", 503),
        ("DEADLINE_EXCEEDED", 503),
        ("UNIMPLEMENTED", 503),
        ("SOMETHING_ELSE", 502),
    ],
)
def test_map_error_uses_grpc_code(name: str, status: int) -> None:
    assert mod._map_error(CodedError(name)).status_code == status


def test_map_error_matches_sdk_message(sdk: mod.Sdk) -> None:
    assert mod._map_error(RuntimeError("sandbox not found")).status_code == 404
    assert mod._map_error(RuntimeError("sandbox already exists")).status_code == 409
    assert mod._map_error(RuntimeError("boom")).status_code == 502


def test_map_error_falls_back_to_class_name() -> None:
    assert "ValueError" in str(mod._map_error(ValueError()))


# --------------------------------------------------------------------- _to_view


def fake_ref(**overrides: object) -> SimpleNamespace:
    base = {
        "id": "sbx-1",
        "name": "box",
        "workspace": "default",
        "status": SimpleNamespace(phase=2, current_policy_version=7, exit_code=0),
        "labels": {"env": "test"},
        "service_urls": {"web": "https://box.example.com"},
        "created_from_workload_template": SimpleNamespace(name="tpl"),
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_to_view_maps_status_and_extras() -> None:
    view = backend()._to_view(fake_ref())  # noqa: SLF001
    assert isinstance(view, SandboxView)
    assert view.id == "sbx-1"
    assert view.phase == "ready"
    assert view.phase_code == 2
    assert view.policy_version == 7
    assert view.exit_code == 0
    assert view.labels == {"env": "test"}
    assert view.service_urls == {"web": "https://box.example.com"}
    assert view.created_from_template == "tpl"


def test_to_view_falls_back_to_workspace_argument() -> None:
    view = backend()._to_view(fake_ref(workspace=None), "team-a")  # noqa: SLF001
    assert view.workspace == "team-a"


def test_to_view_handles_missing_optional_fields() -> None:
    ref = SimpleNamespace(
        id="sbx-2",
        name="bare",
        status=SimpleNamespace(phase=99, current_policy_version=0, exit_code=None),
    )
    view = backend()._to_view(ref, "default")  # noqa: SLF001
    assert view.phase == "unknown"
    assert view.labels == {}
    assert view.service_urls == {}
    assert view.created_from_template is None


# ------------------------------------------------------------------ _build_client


def test_tls_is_none_without_cert_settings(sdk: mod.Sdk) -> None:
    assert backend()._tls(sdk) is None  # noqa: SLF001


def test_tls_config_is_built_when_certificates_are_set(sdk: mod.Sdk) -> None:
    client = backend(gateway_ca_cert="ca.pem", gateway_cert="c.pem", gateway_key="k.pem")
    assert client._tls(sdk) is not None  # noqa: SLF001
    sdk.TlsConfig.assert_called_once_with(
        ca_path=Path("ca.pem"), cert_path=Path("c.pem"), key_path=Path("k.pem")
    )


def test_client_credentials_is_none_without_issuer(sdk: mod.Sdk) -> None:
    assert backend()._client_credentials(sdk) is None  # noqa: SLF001


def test_oidc_on_remote_gateway_requires_tls(sdk: mod.Sdk) -> None:
    client = backend(
        gateway_endpoint="gw.example.com:17670",
        oidc_issuer="https://idp.example.com",
        oidc_client_id="ui",
    )
    with pytest.raises(SettingsError, match="requires TLS"):
        client.client()


def test_oidc_on_loopback_gateway_is_allowed(sdk: mod.Sdk) -> None:
    client = backend(
        gateway_endpoint="127.0.0.1:17670",
        oidc_issuer="https://idp.example.com",
        oidc_client_id="ui",
    )
    assert client.client() is not None


def test_client_is_cached(sdk: mod.Sdk) -> None:
    client = backend(gateway_endpoint="gw.example.com:17670")
    assert client.client() is client.client()
    sdk.SandboxClient.assert_called_once()


def test_client_without_endpoint_uses_active_cluster(sdk: mod.Sdk) -> None:
    client = backend()
    client.client()
    sdk.SandboxClient.from_active_cluster.assert_called_once()


# ------------------------------------------------------------------ SDK 受け口


def test_load_sdk_when_package_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mod, "_sdk_cache", None)
    monkeypatch.setitem(__import__("sys").modules, "openshell", None)
    if importlib.util.find_spec("openshell") is not None:
        pytest.skip("openshell extra is installed, the ImportError path cannot be forced")
    with pytest.raises(BackendUnavailable, match="uv sync --extra openshell"):
        mod.load_sdk()


def test_health_maps_to_payload(sdk: mod.Sdk) -> None:
    client = backend(gateway_endpoint="gw.example.com:17670")
    client._client = MagicMock()  # noqa: SLF001
    client._client.health.return_value = SimpleNamespace(status="serving", version="0.1.2")  # noqa: SLF001
    body = asyncio.run(client.health())
    assert body == {
        "status": "serving",
        "version": "0.1.2",
        "backend": "openshell",
        "detail": "connected to the configured OpenShell gateway",
    }


def test_list_uses_page_size(sdk: mod.Sdk) -> None:
    client = backend(gateway_endpoint="gw.example.com:17670", page_size=7)
    client._client = MagicMock()  # noqa: SLF001
    client._client.list_all.return_value = [fake_ref()]  # noqa: SLF001
    views = asyncio.run(client.list(workspace="team-a"))
    client._client.list_all.assert_called_once_with(workspace="team-a", page_size=7)  # noqa: SLF001
    assert [view.name for view in views] == ["box"]


def test_create_passes_service_exposure(sdk: mod.Sdk) -> None:
    client = backend(gateway_endpoint="gw.example.com:17670")
    client._client = MagicMock()  # noqa: SLF001
    client._client.create.return_value = fake_ref()  # noqa: SLF001
    asyncio.run(
        client.create(
            CreateRequest(
                name="box",
                workspace="default",
                labels={"env": "test"},
                service_port=8000,
                service_name="web",
            )
        )
    )
    kwargs = client._client.create.call_args.kwargs  # noqa: SLF001
    assert kwargs["workspace"] == "default"
    assert kwargs["name"] == "box"
    assert kwargs["labels"] == {"env": "test"}
    assert len(kwargs["service_exposures"]) == 1
    sdk.ServiceExposure.assert_called_once_with(target_port=8000, service="web")


def test_create_omits_exposures_and_labels_when_absent(sdk: mod.Sdk) -> None:
    client = backend(gateway_endpoint="gw.example.com:17670")
    client._client = MagicMock()  # noqa: SLF001
    client._client.create.return_value = fake_ref()  # noqa: SLF001
    asyncio.run(client.create(CreateRequest(name="box", workspace="default")))
    kwargs = client._client.create.call_args.kwargs  # noqa: SLF001
    assert kwargs["labels"] is None
    assert kwargs["service_exposures"] is None


def test_get_uses_name_and_workspace(sdk: mod.Sdk) -> None:
    client = backend(gateway_endpoint="gw.example.com:17670")
    client._client = MagicMock()  # noqa: SLF001
    client._client.get.return_value = fake_ref()  # noqa: SLF001
    asyncio.run(client.get("box", workspace="team-a"))
    client._client.get.assert_called_once_with("box", workspace="team-a")  # noqa: SLF001


def test_delete_forbids_missing(sdk: mod.Sdk) -> None:
    client = backend(gateway_endpoint="gw.example.com:17670")
    client._client = MagicMock()  # noqa: SLF001
    asyncio.run(client.delete("box", workspace="default"))
    client._client.delete.assert_called_once_with(  # noqa: SLF001
        "box", workspace="default", allow_missing=False
    )


def test_aclose_closes_client_once(sdk: mod.Sdk) -> None:
    client = backend(gateway_endpoint="gw.example.com:17670")
    stub = MagicMock()
    client._client = stub  # noqa: SLF001
    asyncio.run(client.aclose())
    stub.close.assert_called_once()
    assert client._client is None  # noqa: SLF001
    asyncio.run(client.aclose())
    stub.close.assert_called_once()


def test_aclose_without_client_is_noop() -> None:
    asyncio.run(backend().aclose())


# ------------------------------------------------------------------ exec_stream


class FakeExecResult:
    def __init__(self, exit_code: int) -> None:
        self.exit_code = exit_code


class FakeChunk:
    def __init__(self, stream: str, data: bytes) -> None:
        self.stream = stream
        self.data = data


def test_exec_stream_translates_chunks(sdk: mod.Sdk, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mod, "load_sdk", lambda: with_exec_result(sdk))
    client = backend(gateway_endpoint="gw.example.com:17670")
    client._client = MagicMock()  # noqa: SLF001
    client._client.exec_stream.return_value = [  # noqa: SLF001
        FakeChunk("stdout", b"hello "),
        FakeChunk("stdout", b"world"),
        FakeChunk("stderr", b"warn"),
        FakeExecResult(0),
    ]

    async def scenario() -> list:
        return [
            event
            async for event in client.exec_stream(
                "box", ExecRequest(command=["echo", "hi"]), workspace="default"
            )
        ]

    events = asyncio.run(scenario())
    assert [(event.type, event.data) for event in events] == [
        ("stdout", "hello "),
        ("stdout", "world"),
        ("stderr", "warn"),
        ("exit", ""),
    ]
    assert events[-1].exit_code == 0
    client._client.exec_stream.assert_called_once_with(  # noqa: SLF001
        "box",
        ["echo", "hi"],
        workspace="default",
        workdir=None,
        timeout_seconds=None,
    )


def test_exec_stream_stops_after_exit(sdk: mod.Sdk, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mod, "load_sdk", lambda: with_exec_result(sdk))
    client = backend(gateway_endpoint="gw.example.com:17670")
    client._client = MagicMock()  # noqa: SLF001
    client._client.exec_stream.return_value = [  # noqa: SLF001
        FakeExecResult(0),
        FakeChunk("stdout", b"ignored"),
    ]

    async def scenario() -> list:
        return [
            event
            async for event in client.exec_stream(
                "box", ExecRequest(command=["ls"]), workspace="default"
            )
        ]

    assert [event.type for event in asyncio.run(scenario())] == ["exit"]


def test_exec_stream_maps_worker_error(sdk: mod.Sdk) -> None:
    client = backend(gateway_endpoint="gw.example.com:17670")
    client._client = MagicMock()  # noqa: SLF001
    client._client.exec_stream.side_effect = RuntimeError("sandbox not found")  # noqa: SLF001

    async def scenario() -> None:
        with pytest.raises(BackendError) as excinfo:
            async for _ in client.exec_stream(
                "box", ExecRequest(command=["ls"]), workspace="default"
            ):
                pass
        assert excinfo.value.status_code == 404

    asyncio.run(scenario())


def test_exec_stream_replaces_invalid_utf8(sdk: mod.Sdk, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mod, "load_sdk", lambda: with_exec_result(sdk))
    client = backend(gateway_endpoint="gw.example.com:17670")
    client._client = MagicMock()  # noqa: SLF001
    client._client.exec_stream.return_value = [  # noqa: SLF001
        FakeChunk("stdout", b"\xff\xfe"),
        FakeExecResult(0),
    ]

    async def scenario() -> str:
        out = ""
        async for event in client.exec_stream(
            "box", ExecRequest(command=["ls"]), workspace="default"
        ):
            out += event.data
        return out

    assert asyncio.run(scenario()) == "\ufffd\ufffd"


# -------------------------------------------------------------- deploy artifacts


def test_policy_is_valid_yaml() -> None:
    yaml = pytest.importorskip("yaml")
    path = Path(__file__).resolve().parents[1] / "policy" / "ui-policy.yaml"
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(document, dict) and document


def test_env_example_lists_auth_and_gateway() -> None:
    text = (Path(__file__).resolve().parents[1] / ".env.example").read_text(encoding="utf-8")
    keys = {
        line.split("=", 1)[0].removeprefix("# ").strip()
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    }
    for required in ("OSUI_AUTH_TOKEN", "OSUI_GATEWAY_ENDPOINT", "OSUI_GATEWAY_CA_CERT"):
        assert required in keys, required


def test_colab_notebook_is_valid_json() -> None:
    path = Path(__file__).resolve().parents[1] / "deploy" / "colab" / "openshell_colab.ipynb"
    notebook = json.loads(path.read_text(encoding="utf-8"))
    assert notebook["nbformat"] == 4
    assert len(notebook["cells"]) >= 1
    for cell in notebook["cells"]:
        json.dumps(cell)
