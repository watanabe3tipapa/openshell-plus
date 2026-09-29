#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

TUNNEL="${OSUI_TUNNEL:-openshell-ui}"
PORT="${OSUI_PORT:-8080}"
MODE="${1:-named}"

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "cloudflared is not installed. Run: brew install cloudflared" >&2
  exit 1
fi

if [ "$MODE" = "quick" ]; then
  export OSUI_SSE_ENABLED=false
  export OSUI_HOST=127.0.0.1
  echo "Quick Tunnel: random trycloudflare.com URL, 200 in-flight request cap, no SSE."
  uv run uvicorn openshell_ui.main:app --host "$OSUI_HOST" --port "$PORT" &
  APP_PID=$!
  trap 'kill "$APP_PID" 2>/dev/null || true' EXIT
  sleep 2
  exec cloudflared tunnel --url "http://127.0.0.1:${PORT}"
fi

if [ -z "${OSUI_AUTH_TOKEN:-}" ]; then
  OSUI_AUTH_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
  export OSUI_AUTH_TOKEN
  echo "generated OSUI_AUTH_TOKEN=${OSUI_AUTH_TOKEN}"
fi

export OSUI_HOST=127.0.0.1
uv run uvicorn openshell_ui.main:app --host "$OSUI_HOST" --port "$PORT" &
APP_PID=$!
trap 'kill "$APP_PID" 2>/dev/null || true' EXIT
sleep 2

CONFIG="${OSUI_CLOUDFLARED_CONFIG:-$HOME/.cloudflared/config.yml}"
if [ ! -f "$CONFIG" ]; then
  echo "Missing $CONFIG. Copy deploy/cloudflared/config.yml.example and fill in the tunnel id." >&2
  exit 1
fi

echo "Starting named tunnel ${TUNNEL} from ${CONFIG}"
exec cloudflared tunnel --config "$CONFIG" run "$TUNNEL"
