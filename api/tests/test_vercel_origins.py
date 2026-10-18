"""Only trusted platform deployment hosts may receive cookie-authenticated writes."""
import pytest
from starlette.requests import Request
from api.app.accounts import browser_origin
from api.app.security import PolicyError


def request(origin):
    return Request({'type':'http','headers':[(b'origin',origin.encode()),(b'x-safeledger-client',b'web')]})


def test_preview_origin_is_exact_and_platform_controlled(monkeypatch):
    monkeypatch.setenv('VERCEL','1');monkeypatch.setenv('VERCEL_URL','safeledger-preview-challanger2.vercel.app')
    browser_origin(request('https://safeledger-preview-challanger2.vercel.app'))
    for origin in ['https://evil.vercel.app','http://safeledger-preview-challanger2.vercel.app','https://safeledger-preview-challanger2.vercel.app.evil.example']:
        with pytest.raises(PolicyError):browser_origin(request(origin))


@pytest.mark.parametrize('value',['evil.example','evil.example/path','bad.vercel.app@evil.example','safe.vercel.app/path','safe.vercel.app:443','safe.vercel.app?x=1'])
def test_invalid_platform_hostname_is_not_allowed(monkeypatch,value):
    monkeypatch.setenv('VERCEL','1');monkeypatch.setenv('VERCEL_URL',value)
    with pytest.raises(PolicyError):browser_origin(request('https://'+value))
