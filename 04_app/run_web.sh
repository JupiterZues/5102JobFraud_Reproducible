#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

uvicorn server:app \
  --host "${HOST:-0.0.0.0}" \
  --port "${PORT:-8501}"
