"""Vercel entrypoint: preserve Render signing identity and publish the UI to CDN."""
import os
import re
from pathlib import Path

from fastapi.staticfiles import StaticFiles

# Match render_start.sh exactly; never generate or replace an existing key.
key = os.environ.get("SAFELEDGER_SIGNING_KEY", "")
if re.fullmatch(r"[0-9a-f]{32}", key):
    os.environ["SAFELEDGER_SIGNING_KEY"] = key + key

from api.app.main import app  # noqa: E402

# API routes are declared first. Vercel promotes these public build files to
# its CDN and removes them from the function bundle. No records are mounted.
app.mount("/", StaticFiles(
    directory=Path(__file__).resolve().parents[1] / "web" / "dist",
    html=True,
    check_dir=False,
), name="frontend")
