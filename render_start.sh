#!/bin/bash
# Render start command: seed data first, then start FastAPI.
# Called with: bash render_start.sh
set -e
echo "[start] Running production seed..."
python scripts/production_seed.py
echo "[start] Starting uvicorn..."
exec python -m uvicorn api.app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
