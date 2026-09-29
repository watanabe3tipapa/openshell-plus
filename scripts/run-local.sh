#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

export OSUI_HOST="${OSUI_HOST:-127.0.0.1}"
export OSUI_PORT="${OSUI_PORT:-8080}"
export OSUI_WORKSPACE="${OSUI_WORKSPACE:-default}"

case "${OSUI_HOST}" in
  127.0.0.1|localhost|::1) loopback=1 ;;
  *) loopback=0 ;;
esac

if [ "$loopback" -eq 0 ] && [ -z "${OSUI_AUTH_TOKEN:-}" ]; then
  OSUI_AUTH_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
  export OSUI_AUTH_TOKEN
  echo "generated OSUI_AUTH_TOKEN=${OSUI_AUTH_TOKEN}"
  echo "paste it into the dashboard when it asks for a token"
fi

uv sync --all-extras
echo "serving http://${OSUI_HOST}:${OSUI_PORT} (workspace=${OSUI_WORKSPACE})"

if [ "$loopback" -eq 0 ]; then
  exec uv run uvicorn openshell_ui.main:app --host "$OSUI_HOST" --port "$OSUI_PORT" --log-level info
else
  exec uv run uvicorn openshell_ui.main:app --host "$OSUI_HOST" --port "$OSUI_PORT" --reload
fi
