#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if ! command -v vercel >/dev/null 2>&1; then
  echo "vercel CLI is not installed. Run: npm i -g vercel" >&2
  exit 1
fi

if [ -z "${VERCEL_ORG_ID:-}" ] && [ ! -d .vercel ]; then
  echo "No Vercel project linked. Run: vercel link" >&2
  exit 1
fi

if ! vercel env ls 2>/dev/null | grep -q "OSUI_AUTH_TOKEN"; then
  echo "OSUI_AUTH_TOKEN is not set in the Vercel project." >&2
  echo "Add it before the first deploy:" >&2
  echo "  vercel env add OSUI_AUTH_TOKEN production" >&2
  exit 1
fi

echo "Deploying to Vercel (backend will be demo unless OSUI_GATEWAY_ENDPOINT is set)."
vercel deploy --prod "$@"
