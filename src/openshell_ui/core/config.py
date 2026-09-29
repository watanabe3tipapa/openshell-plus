from __future__ import annotations

import ipaddress
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SettingsError(RuntimeError):
    pass


def is_loopback_host(host: str) -> bool:
    candidate = host.strip().strip("[]").lower()
    if candidate in ("localhost", "localhost.localdomain", ""):
        return True
    try:
        return ipaddress.ip_address(candidate).is_loopback
    except ValueError:
        return False


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="OSUI_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "OpenShell UI"

    mode: str | None = None
    host: str = "127.0.0.1"
    port: int = 8080
    debug: bool = False
    log_level: str = "info"

    auth_token: str | None = None

    demo: bool = False
    require_gateway: bool = False

    workspace: str = "default"
    page_size: int = 100
    exec_default_timeout: int = 60
    exec_max_timeout: int = 1800

    sse_enabled: bool = True
    cors_origins: list[str] = Field(default_factory=list)

    gateway_endpoint: str | None = None
    gateway_timeout: float = 30.0
    gateway_cluster: str | None = None
    gateway_ca_cert: Path | None = None
    gateway_cert: Path | None = None
    gateway_key: Path | None = None
    gateway_insecure: bool = False

    oidc_issuer: str | None = None
    oidc_client_id: str | None = None
    oidc_client_secret: str | None = None
    oidc_audience: str | None = None
    oidc_scopes: list[str] = Field(default_factory=list)

    @property
    def auth_required(self) -> bool:
        return bool(self.auth_token)

    @property
    def public_bind(self) -> bool:
        return not is_loopback_host(self.host)

    def gateway_host(self) -> str | None:
        return self.gateway_endpoint

    def validate_startup(self) -> None:
        if self.public_bind and not self.auth_token:
            raise SettingsError(
                f"refusing to bind {self.host}: set OSUI_AUTH_TOKEN before exposing the app, "
                "or keep the default OSUI_HOST=127.0.0.1"
            )
        if (self.gateway_cert is None) != (self.gateway_key is None):
            raise SettingsError(
                "OSUI_GATEWAY_CERT and OSUI_GATEWAY_KEY must be set together for mTLS"
            )
        if self.oidc_client_secret and not self.oidc_issuer:
            raise SettingsError("OSUI_OIDC_CLIENT_SECRET requires OSUI_OIDC_ISSUER")
        if self.oidc_issuer and not self.oidc_client_id:
            raise SettingsError("OSUI_OIDC_ISSUER requires OSUI_OIDC_CLIENT_ID")
        if self.exec_default_timeout > self.exec_max_timeout:
            raise SettingsError("OSUI_EXEC_DEFAULT_TIMEOUT cannot exceed OSUI_EXEC_MAX_TIMEOUT")


@lru_cache
def get_settings() -> Settings:
    return Settings()
