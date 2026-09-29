from __future__ import annotations

import pytest

from openshell_ui.core.config import Settings, SettingsError, is_loopback_host
from openshell_ui.core.mode import RunMode, detect_mode
from tests.helpers import make_settings


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("127.0.0.1", True),
        ("127.1.2.3", True),
        ("::1", True),
        ("[::1]", True),
        ("localhost", True),
        ("LOCALHOST", True),
        ("", True),
        ("0.0.0.0", False),
        ("192.168.1.10", False),
        ("example.com", False),
    ],
)
def test_is_loopback_host(host: str, expected: bool) -> None:
    assert is_loopback_host(host) is expected


def test_public_bind_follows_host() -> None:
    assert make_settings(host="127.0.0.1").public_bind is False
    assert make_settings(host="0.0.0.0").public_bind is True


def test_auth_required_follows_token() -> None:
    assert make_settings().auth_required is False
    assert make_settings(auth_token="t").auth_required is True


def test_public_bind_without_token_is_refused() -> None:
    with pytest.raises(SettingsError, match="refusing to bind"):
        make_settings(host="0.0.0.0").validate_startup()


def test_public_bind_with_token_is_allowed() -> None:
    make_settings(host="0.0.0.0", auth_token="t").validate_startup()


def test_mtls_cert_and_key_must_be_paired() -> None:
    with pytest.raises(SettingsError, match="must be set together"):
        make_settings(gateway_cert="client.pem").validate_startup()
    with pytest.raises(SettingsError, match="must be set together"):
        make_settings(gateway_key="client.key").validate_startup()
    make_settings(gateway_cert="client.pem", gateway_key="client.key").validate_startup()


def test_oidc_client_secret_requires_issuer() -> None:
    with pytest.raises(SettingsError, match="requires OSUI_OIDC_ISSUER"):
        make_settings(oidc_client_secret="shh").validate_startup()


def test_oidc_issuer_requires_client_id() -> None:
    with pytest.raises(SettingsError, match="requires OSUI_OIDC_CLIENT_ID"):
        make_settings(oidc_issuer="https://idp.example.com").validate_startup()


def test_exec_default_timeout_cannot_exceed_max() -> None:
    with pytest.raises(SettingsError, match="cannot exceed"):
        make_settings(exec_default_timeout=100, exec_max_timeout=60).validate_startup()
    make_settings(exec_default_timeout=60, exec_max_timeout=60).validate_startup()


def test_env_prefix_is_applied(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OSUI_WORKSPACE", "team-a")
    monkeypatch.setenv("OSUI_PAGE_SIZE", "25")
    monkeypatch.setenv("OSUI_SSE_ENABLED", "false")
    settings = Settings()
    assert settings.workspace == "team-a"
    assert settings.page_size == 25
    assert settings.sse_enabled is False


def test_detect_mode_prefers_explicit_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VERCEL", "1")
    assert detect_mode("colab") is RunMode.COLAB


def test_detect_mode_reads_osui_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OSUI_MODE", "CLOUDFLARE")
    assert detect_mode() is RunMode.CLOUDFLARE


def test_detect_mode_falls_back_to_local_for_unknown_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OSUI_MODE", "not-a-mode")
    assert detect_mode() is RunMode.LOCAL


def test_detect_mode_detects_vercel(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VERCEL", "1")
    assert detect_mode() is RunMode.VERCEL


def test_detect_mode_detects_sandbox(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENSHELL_SANDBOX_ID", "sbx-1")
    assert detect_mode() is RunMode.SANDBOX


def test_detect_mode_detects_colab(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COLAB_RELEASE_TAG", "release")
    assert detect_mode() is RunMode.COLAB


def test_detect_mode_defaults_to_local() -> None:
    assert detect_mode() is RunMode.LOCAL
