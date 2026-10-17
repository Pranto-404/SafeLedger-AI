#!/bin/bash
# Render start command: seed data first, then start FastAPI.
# Called with: bash render_start.sh
set -e
if [ -z "$SAFELEDGER_SIGNING_KEY" ]; then
    export SAFELEDGER_SIGNING_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
    echo "[start] Auto-generated SAFELEDGER_SIGNING_KEY"
fi
echo "[start] Running production seed..."
python scripts/production_seed.py
echo "[start] Starting uvicorn..."
exec python -m uvicorn api.app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
