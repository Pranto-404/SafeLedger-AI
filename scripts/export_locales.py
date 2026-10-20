"""Download finished interface translations from the running server and save them as static files the site serves directly.

Usage: python scripts/export_locales.py [base_url] [language ...]
The server translates once (Google Translate when a key is set, otherwise the cloud model) and caches the result; this script
only reads, one request at a time with a pause, so it is safe to run against the live site. Files are written to web/public/locales/."""
import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'web' / 'public' / 'locales'
BASE = sys.argv[1].rstrip('/') if len(sys.argv) > 1 else 'https://capzoryx-copilot.vercel.app'
ALL = ['bn', 'zh-CN', 'zh-TW', 'ja', 'ko', 'hi', 'ur', 'ar', 'fa', 'he', 'es', 'fr', 'pt', 'de', 'it', 'ru', 'tr', 'id', 'ms', 'th', 'vi', 'ta', 'te', 'mr', 'pa', 'gu', 'kn', 'ml', 'ne', 'si', 'nl', 'pl', 'uk', 'el', 'sw', 'fil']
wanted = sys.argv[2:] or ALL


def fetch(code):
    with urllib.request.urlopen(urllib.request.Request(f'{BASE}/api/i18n?lang={code}', headers={'User-Agent': 'capzoryx-locale-export'}), timeout=90) as r:
        return json.load(r)


OUT.mkdir(parents=True, exist_ok=True)
for code in wanted:
    body = None
    for attempt in range(40):
        try:body = fetch(code)
        except Exception as exc:
            print(code, 'error', type(exc).__name__)
            time.sleep(8)
            continue
        print(code, 'missing', body['missing'], flush=True)
        if body['missing'] == 0:break
        time.sleep(6)
    if body and body['missing'] == 0:
        (OUT / f'{code}.json').write_text(json.dumps({'version': body['version'], 'strings': body['strings']}, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
        print(code, 'saved', len(body['strings']), flush=True)
    else:
        print(code, 'skipped (not complete)', flush=True)
print('EXPORT_DONE')
