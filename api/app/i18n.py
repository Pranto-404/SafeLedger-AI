"""Interface languages. English is the source text. For any other language the fixed list of interface strings in
ui_strings.json is translated once by the cloud model and cached in the database, so every later visitor gets it instantly.

Only strings from that list are ever translated (never text sent by a client), the language must be on the allow-list,
and untranslated strings simply stay in English. Nothing here sees account data."""
import hashlib
import json
import re
import threading
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from api.app import cloud, security as sec
from api.app.agents.errors import ProviderError
from api.app.routes import db_connection

router = APIRouter(prefix='/api')

# code: (English name, native name, right-to-left)
LANGUAGES = {
    'en': ('English', 'English', False), 'bn': ('Bangla', 'বাংলা', False), 'zh-CN': ('Simplified Chinese', '简体中文', False),
    'zh-TW': ('Traditional Chinese', '繁體中文', False), 'ja': ('Japanese', '日本語', False), 'ko': ('Korean', '한국어', False),
    'hi': ('Hindi', 'हिन्दी', False), 'ur': ('Urdu', 'اردو', True), 'ar': ('Arabic', 'العربية', True), 'fa': ('Persian', 'فارسی', True),
    'he': ('Hebrew', 'עברית', True), 'es': ('Spanish', 'Español', False), 'fr': ('French', 'Français', False), 'pt': ('Portuguese', 'Português', False),
    'de': ('German', 'Deutsch', False), 'it': ('Italian', 'Italiano', False), 'ru': ('Russian', 'Русский', False), 'tr': ('Turkish', 'Türkçe', False),
    'id': ('Indonesian', 'Bahasa Indonesia', False), 'ms': ('Malay', 'Bahasa Melayu', False), 'th': ('Thai', 'ไทย', False), 'vi': ('Vietnamese', 'Tiếng Việt', False),
    'ta': ('Tamil', 'தமிழ்', False), 'te': ('Telugu', 'తెలుగు', False), 'mr': ('Marathi', 'मराठी', False), 'pa': ('Punjabi', 'ਪੰਜਾਬੀ', False),
    'gu': ('Gujarati', 'ગુજરાતી', False), 'kn': ('Kannada', 'ಕನ್ನಡ', False), 'ml': ('Malayalam', 'മലയാളം', False), 'ne': ('Nepali', 'नेपाली', False),
    'si': ('Sinhala', 'සිංහල', False), 'nl': ('Dutch', 'Nederlands', False), 'pl': ('Polish', 'Polski', False), 'uk': ('Ukrainian', 'Українська', False),
    'el': ('Greek', 'Ελληνικά', False), 'sw': ('Swahili', 'Kiswahili', False), 'fil': ('Filipino', 'Filipino', False),
}
BATCH = 60
_STRINGS = json.loads((Path(__file__).with_name('ui_strings.json')).read_text(encoding='utf-8'))
VERSION = hashlib.sha256(json.dumps(_STRINGS, ensure_ascii=False).encode()).hexdigest()[:12]
_LOCKS = {code: threading.Lock() for code in LANGUAGES}
_PLACEHOLDER = re.compile(r'\{[A-Za-z0-9_]+\}')


def schema(db):
    db.executescript('CREATE TABLE IF NOT EXISTS i18n_text(lang TEXT NOT NULL, key_hash TEXT NOT NULL, text TEXT NOT NULL, PRIMARY KEY(lang,key_hash));')


def _key(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]


def _clean(source, value):
    """Accept a translation only if it is plain text of a sensible size and keeps every {placeholder}."""
    if not isinstance(value, str):return None
    value = re.sub(r'\s+', ' ', re.sub(r'[\u0000-\u001f\u007f]+', ' ', value)).strip()
    if not value or len(value) > max(40, len(source) * 4) or len(value) > 600 or '<' in value or '>' in value:return None
    if sorted(_PLACEHOLDER.findall(source)) != sorted(_PLACEHOLDER.findall(value)):return None
    return value


def _translate_batch(language, batch):
    listing = '\n'.join(f'{i + 1}. {text}' for i, text in enumerate(batch))
    reply = cloud.complete([
        {'role': 'system', 'content': f'You translate short user-interface text for a small-business finance web app from English to {language}. '
         'Use natural, concise wording a shopkeeper understands. Keep the brand name Capzoryx Copilot, the abbreviations PDF, 2FA, OCR, and every {placeholder} exactly as written. '
         'Do not add notes. Return only a JSON object mapping each item number (as a string) to its translation.'},
        {'role': 'user', 'content': listing}], max_tokens=6000, json_mode=True, timeout=40)
    data = cloud.parse_json_object(reply)
    found = {}
    for i, text in enumerate(batch):
        value = _clean(text, data.get(str(i + 1)))
        if value is not None:found[text] = value
    return found


@router.get('/i18n')
def interface_text(lang: str, db=Depends(db_connection)):
    if lang not in LANGUAGES:raise HTTPException(status_code=404, detail={'error': {'code': 'LANGUAGE_NOT_SUPPORTED'}})
    english, native, rtl = LANGUAGES[lang]
    base = dict(language=lang, name=native, rtl=rtl, version=VERSION, simulation_only=True)
    if lang == 'en':return dict(base, strings={}, missing=0)
    sec.budgets(db, [('i18n-read-all', 240)])
    have = {key: text for key, text in db.execute('SELECT key_hash,text FROM i18n_text WHERE lang=?', (lang,)).fetchall()}
    missing = [s for s in _STRINGS if _key(s) not in have]
    if missing and cloud.configured() and _LOCKS[lang].acquire(blocking=False):
        try:
            sec.budgets(db, [('i18n-translate-all', 12)])
            found = _translate_batch(english, missing[:BATCH])
            if found:
                with sec.transaction(db):
                    for source, text in found.items():
                        db.execute('INSERT OR REPLACE INTO i18n_text(lang,key_hash,text) VALUES (?,?,?)', (lang, _key(source), text))
                have.update({_key(s): t for s, t in found.items()})
                missing = [s for s in _STRINGS if _key(s) not in have]
        except (ProviderError, HTTPException):
            pass  # strings stay in English until the next attempt; nothing is broken
        finally:
            _LOCKS[lang].release()
    strings = {s: have[_key(s)] for s in _STRINGS if _key(s) in have}
    return dict(base, strings=strings, missing=len(missing))
