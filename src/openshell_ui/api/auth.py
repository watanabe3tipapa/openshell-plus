from __future__ import annotations

import secrets

from fastapi import Depends, HTTPException, Request

from openshell_ui.core.config import Settings

SUBPROTOCOL_PREFIX = "bearer."


def token_from_subprotocol(value: str | None) -> str | None:
    if not value:
        return None
    for part in value.split(","):
        candidate = part.strip()
        if candidate.lower().startswith(SUBPROTOCOL_PREFIX):
            token = candidate[len(SUBPROTOCOL_PREFIX) :].strip()
            if token:
                return token
    return None


def extract_token(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        candidate = header[7:].strip()
        if candidate:
            return candidate
    token = token_from_subprotocol(request.headers.get("sec-websocket-protocol"))
    if token:
        return token
    return request.query_params.get("token") or None


def token_matches(settings: Settings, provided: str | None) -> bool:
    if not settings.auth_required:
        return True
    if not provided:
        return False
    return secrets.compare_digest(provided, settings.auth_token or "")


async def require_auth(request: Request) -> None:
    if not token_matches(request.app.state.settings, extract_token(request)):
        raise HTTPException(
            status_code=401,
            detail="invalid or missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )


auth_dependency = Depends(require_auth)
