#!/usr/bin/env bash
# Azure App Service / container startup script
set -euo pipefail

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
WORKERS="${WORKERS:-1}"
LOG_LEVEL="${LOG_LEVEL:-info}"

echo "Starting PII Masking API on ${HOST}:${PORT} with ${WORKERS} worker(s)..."

exec uvicorn app.main:app \
  --host "${HOST}" \
  --port "${PORT}" \
  --workers "${WORKERS}" \
  --log-level "${LOG_LEVEL,,}" \
  --proxy-headers \
  --forwarded-allow-ips="*"
