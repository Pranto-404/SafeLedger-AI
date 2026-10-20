"""Interface languages: allow-listed languages only, only listed strings are translated, results are cached and sanitised."""
import json
import re
import httpx
import pytest
from api.tests.test_accounts import world, signup
from api.app import cloud, i18n


@pytest.fixture
def translator(monkeypatch):
    for key, value in dict(SAFELEDGER_LLM_PROFILE='gemini_free', SAFELEDGER_LLM_BASE_URL='https://generativelanguage.googleapis.com/v1beta/openai', SAFELEDGER_LLM_MODEL='gemini-3.5-flash-lite',
                           SAFELEDGER_LLM_API_KEY='test-key-not-real-12345', SAFELEDGER_LLM_ALLOWED_HOSTS='generativelanguage.googleapis.com', SAFELEDGER_LLM_FREE_TIER_CONFIRMED='1').items():
        monkeypatch.setenv(key, value)
    seen = {'calls': [], 'mode': 'good'}
    def handler(request):
        body = json.loads(request.content)
        user = body['messages'][1]['content']
        seen['calls'].append((body['messages'][0]['content'], user))
        rows = re.findall(r'^(\d+)\. (.*)$', user, flags=re.M)
        if seen['mode'] == 'good':out = {n: '«' + text + '»' for n, text in rows}
        elif seen['mode'] == 'evil':out = {n: '<script>alert(1)</script>' for n, text in rows}
        elif seen['mode'] == 'drop_placeholders':out = {n: 'translated' for n, text in rows}
        else:return httpx.Response(429, json={})
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(out, ensure_ascii=False)}}], 'usage': {'prompt_tokens': 5, 'completion_tokens': 5}})
    monkeypatch.setattr(cloud, 'TRANSPORT', httpx.MockTransport(handler))
    return seen


def test_english_and_unknown_languages(world):
    c, _ = world
    assert c.get('/api/i18n?lang=en').json()['strings'] == {}
    assert c.get('/api/i18n?lang=xx').status_code == 404
    assert c.get('/api/i18n?lang=' + 'a' * 50).status_code == 404
    assert c.get('/api/i18n').status_code == 422
    langs = i18n.LANGUAGES
    assert {'zh-CN', 'ja', 'hi', 'ur', 'ar', 'bn'} <= set(langs) and langs['ar'][2] and langs['ur'][2] and not langs['ja'][2]


def test_translation_is_batched_cached_and_only_for_listed_strings(world, translator):
    c, _ = world
    first = c.get('/api/i18n?lang=ja').json()
    assert first['missing'] > 0 and 0 < len(first['strings']) <= i18n.BATCH and first['rtl'] is False and first['name'] == '日本語'
    assert all(k in i18n._STRINGS and v == '«' + k + '»' for k, v in first['strings'].items())
    assert 'Japanese' in translator['calls'][0][0] and len(translator['calls']) == 1
    total = len(i18n._STRINGS)
    for _ in range(20):
        body = c.get('/api/i18n?lang=ja').json()
        if body['missing'] == 0:break
    assert body['missing'] == 0 and len(body['strings']) == total
    calls = len(translator['calls'])
    again = c.get('/api/i18n?lang=ja').json()  # fully cached: no more model calls, same text
    assert again['strings'] == body['strings'] and len(translator['calls']) == calls
    assert c.get('/api/i18n?lang=ar').json()['rtl'] is True


def test_unsafe_or_broken_translations_are_dropped_and_english_stays(world, translator):
    c, _ = world
    translator['mode'] = 'evil'
    assert c.get('/api/i18n?lang=fr').json()['strings'] == {}
    translator['mode'] = 'drop_placeholders'
    body = c.get('/api/i18n?lang=de').json()
    with_placeholder = [s for s in i18n._STRINGS[:i18n.BATCH] if '{' in s]
    assert all(s not in body['strings'] for s in with_placeholder) and body['strings']  # placeholders must survive translation
    translator['mode'] = 'quota'
    resp = c.get('/api/i18n?lang=es')
    assert resp.status_code == 200 and resp.json()['strings'] == {} and resp.json()['missing'] == len(i18n._STRINGS)


def test_clean_rules():
    assert i18n._clean('Hello {name}', 'Hola {name}') == 'Hola {name}'
    assert i18n._clean('Hello {name}', 'Hola') is None
    assert i18n._clean('Hi', '<b>Hola</b>') is None
    assert i18n._clean('Hi', 'x' * 700) is None
    assert i18n._clean('Hi', 'Hola\n\n  mundo') == 'Hola mundo'
    assert i18n._clean('Hi', 5) is None


def test_language_and_display_currency_are_saved_on_the_account(world):
    c, _ = world
    signup(c, 'lang_user')
    p = c.get('/api/account/profile').json()
    assert p['display_currency'] == 'USD' and p['language'] == 'en'
    assert c.post('/api/account/profile', json={'display_currency': 'EUR', 'language': 'ja'}).status_code == 200
    p = c.get('/api/account/profile').json()
    assert p['display_currency'] == 'EUR' and p['language'] == 'ja'
    assert c.post('/api/account/profile', json={'display_currency': 'euro'}).status_code == 422
    assert c.post('/api/account/profile', json={'language': 'klingon'}).status_code == 422


def test_google_translation_is_used_when_a_key_is_set_and_is_fast(world, monkeypatch):
    c, _ = world
    monkeypatch.setenv('SAFELEDGER_GOOGLE_TRANSLATE_KEY', 'test-google-key')
    seen = []
    def handler(request):
        body = json.loads(request.content)
        seen.append((str(request.url), request.headers.get('x-goog-api-key'), body))
        rows = [{'translatedText': 'T:' + re.sub(r'</?span[^>]*>', '', q).replace('&', '&amp;')} for q in body['q']]
        return httpx.Response(200, json={'data': {'translations': rows}})
    monkeypatch.setattr(i18n, 'GOOGLE_TRANSPORT', httpx.MockTransport(handler))
    body = c.get('/api/i18n?lang=ja').json()
    assert body['missing'] == 0 and len(body['strings']) == len(i18n._STRINGS)  # one request cycle fills the whole list
    assert all(url.startswith('https://translation.googleapis.com/') and key == 'test-google-key' and b['target'] == 'ja' and b['format'] == 'html' for url, key, b in seen)
    assert len(seen) == -(-len(i18n._STRINGS) // i18n.GOOGLE_BATCH)
    assert any('translate="no"' in q for _, _, b in seen for q in b['q'])  # placeholders and brand names are fenced off
    assert body['strings']['Sign in'] == 'T:Sign in'
    calls = len(seen)
    c.get('/api/i18n?lang=ja')
    assert len(seen) == calls  # cached


def test_google_failure_falls_back_to_english_without_breaking(world, monkeypatch):
    c, _ = world
    monkeypatch.setenv('SAFELEDGER_GOOGLE_TRANSLATE_KEY', 'test-google-key')
    monkeypatch.setattr(i18n, 'GOOGLE_TRANSPORT', httpx.MockTransport(lambda r: httpx.Response(403, json={})))
    resp = c.get('/api/i18n?lang=de')
    assert resp.status_code == 200 and resp.json()['strings'] == {} and resp.json()['missing'] == len(i18n._STRINGS)
