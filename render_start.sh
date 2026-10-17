#!/bin/bash
# Render start command: seed data first, then start FastAPI.
# Called with: bash render_start.sh
set -e
if [ -z "$SAFELEDGER_SIGNING_KEY" ] || [ ${#SAFELEDGER_SIGNING_KEY} -ne 64 ]; then
    if [ ${#SAFELEDGER_SIGNING_KEY} -eq 32 ]; then
        export SAFELEDGER_SIGNING_KEY="${SAFELEDGER_SIGNING_KEY}${SAFELEDGER_SIGNING_KEY}"
        echo "[start] Expanded 32-char key to 64-char SAFELEDGER_SIGNING_KEY"
    else
        export SAFELEDGER_SIGNING_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
        echo "[start] Auto-generated 64-char SAFELEDGER_SIGNING_KEY"
    fi
fi
echo "[start] Running production seed..."
python scripts/production_seed.py
echo "[start] Starting uvicorn..."
exec python -m uvicorn api.app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
