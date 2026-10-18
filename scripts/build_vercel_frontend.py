"""Publish only the built frontend to Vercel's CDN; never copy records or secrets."""
from pathlib import Path
import shutil
root=Path(__file__).resolve().parents[1]
source=root/'web/dist'
if not (source/'index.html').is_file():raise SystemExit('Build the web frontend first')
target=root/'public'
if target.exists():shutil.rmtree(target)
shutil.copytree(source,target)
print('Frontend static assets prepared for Vercel CDN')
