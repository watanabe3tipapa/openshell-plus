from __future__ import annotations

import importlib.util
import os
import sys
from enum import StrEnum


class RunMode(StrEnum):
    LOCAL = "local"
    CLOUDFLARE = "cloudflare"
    VERCEL = "vercel"
    COLAB = "colab"
    SANDBOX = "sandbox"


def in_colab() -> bool:
    if os.environ.get("COLAB_RELEASE_TAG"):
        return True
    if "google.colab" in sys.modules:
        return True
    try:
        return importlib.util.find_spec("google.colab") is not None
    except (ImportError, ValueError):
        return False


def detect_mode(override: str | None = None) -> RunMode:
    raw = (override or os.environ.get("OSUI_MODE") or "").strip().lower()
    if raw:
        try:
            return RunMode(raw)
        except ValueError:
            pass
    if os.environ.get("VERCEL") or os.environ.get("VERCEL_ENV"):
        return RunMode.VERCEL
    if os.environ.get("OPENSHELL_SANDBOX_ID"):
        return RunMode.SANDBOX
    if in_colab():
        return RunMode.COLAB
    return RunMode.LOCAL
