#!/bin/bash
# Keep the signing identity stable across restarts; never invent a replacement key.
set -euo pipefail
key="${SAFELEDGER_SIGNING_KEY:-}"
if [[ "$key" =~ ^[0-9a-f]{32}$ ]]; then
    # Preserve the exact legacy key derivation used by existing signed demo data.
    export SAFELEDGER_SIGNING_KEY="${key}${key}"
    echo "[start] Using legacy signing-key compatibility; retain this key for existing audit data."
elif [[ ! "$key" =~ ^[0-9a-f]{64}$ ]]; then
    echo "[start] ERROR: stable 64-character lowercase hex SAFELEDGER_SIGNING_KEY required." >&2
    exit 1
fi
if [[ "${SAFELEDGER_LEGACY_DEMO_SEED:-0}" == "1" ]]; then
    echo "[start] Preparing legacy private demo..."
    python scripts/production_seed.py
fi
echo "[start] Public workspaces initialize on startup."
echo "[start] Starting uvicorn..."
exec python -m uvicorn api.app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
