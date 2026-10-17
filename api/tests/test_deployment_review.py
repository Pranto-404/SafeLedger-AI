"""Regression checks for deployment identity, request budget and session recovery."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import httpx
import pytest
from fastapi.testclient import TestClient
from api.app.main import app
from api.app import security as sec
from api.app.agents.provider import ChatProvider, ProviderError
from scripts import production_seed, renew_demo_sessions

ROOT = Path(__file__).resolve().parents[2]


def test_render_commit_identifies_real_source(monkeypatch):
    monkeypatch.setenv('RENDER_GIT_COMMIT', 'current-render-commit')
    monkeypatch.setenv('SAFELEDGER_BUILD_COMMIT', 'stale-manual-value')
    assert TestClient(app).get('/api/health').json()['build_commit'] == 'current-render-commit'


@pytest.mark.parametrize('status', [429, 500, 502, 503, 504])
def test_real_mode_never_hides_http_retry(monkeypatch, status):
    monkeypatch.setenv('SAFELEDGER_LLM_API_KEY', 'test-key')
    monkeypatch.setenv('SAFELEDGER_LLM_FREE_TIER_CONFIRMED', '1')
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(status)
    provider = ChatProvider(transport=httpx.MockTransport(handler))
    provider.is_mock = False  # The former bug retried only in the non-mock branch.
    with pytest.raises(ProviderError):
        provider.complete([{'role': 'user', 'content': 'balance'}])
    assert len(calls) == provider.calls == 1


@pytest.mark.parametrize('key', ['', 'x'*64, '1'*31, '1'*65])
def test_invalid_startup_key_stops_before_seed(key):
    result = subprocess.run(['bash', 'render_start.sh'], cwd=ROOT,
                            env={**os.environ, 'SAFELEDGER_SIGNING_KEY': key}, capture_output=True, text=True)
    assert result.returncode == 1
    assert 'stable 64-character' in result.stderr
    assert 'Running production seed' not in result.stdout


def test_private_seed_and_expired_session_recovery_preserve_data(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv('SAFELEDGER_DB', str(tmp_path/'data.sqlite3'))
    monkeypatch.setenv('SAFELEDGER_SIGNING_KEY', 'a'*64)
    monkeypatch.setenv('SAFELEDGER_SESSION_FILE', str(tmp_path/'first.json'))
    production_seed.seed_if_empty()
    first = json.loads((tmp_path/'first.json').read_text())
    assert all(value not in capsys.readouterr().out for value in first['bearer_tokens'].values())
    assert (tmp_path/'first.json').stat().st_mode & 0o777 == 0o600
    # A later startup must preserve the existing dataset and credential file.
    before = (tmp_path/'first.json').read_bytes()
    production_seed.seed_if_empty()
    assert (tmp_path/'first.json').read_bytes() == before
    monkeypatch.setattr(renew_demo_sessions, 'ROOT', tmp_path)
    target = tmp_path/'.private'/'renewed.json'
    with sqlite3.connect(tmp_path/'data.sqlite3') as db:
        db.execute('UPDATE security_sessions SET expires_at=0')
        dataset = db.execute('SELECT * FROM financial_datasets').fetchall()
    renew_demo_sessions.renew(target)
    recovered = json.loads(target.read_text())
    assert all(value not in capsys.readouterr().out for value in recovered['bearer_tokens'].values())
    with sqlite3.connect(tmp_path/'data.sqlite3') as db:
        assert db.execute('SELECT * FROM financial_datasets').fetchall() == dataset
        for role, token in recovered['bearer_tokens'].items():
            assert sec.resolve_hash(db, hashlib.sha256(token.encode()).hexdigest()).role == role
        with pytest.raises(sec.PolicyError):
            sec.resolve_hash(db, hashlib.sha256(first['bearer_tokens']['owner'].encode()).hexdigest())
        assert db.execute('SELECT count(*) FROM postings').fetchone()[0] == 0
    with pytest.raises(FileExistsError):
        renew_demo_sessions.renew(target)


def test_session_recovery_cannot_change_disabled_identity(tmp_path, monkeypatch):
    monkeypatch.setenv('SAFELEDGER_DB', str(tmp_path/'data.sqlite3'))
    monkeypatch.setenv('SAFELEDGER_SIGNING_KEY', 'a'*64)
    monkeypatch.setenv('SAFELEDGER_SESSION_FILE', str(tmp_path/'first.json'))
    production_seed.seed_if_empty()
    with sqlite3.connect(tmp_path/'data.sqlite3') as db:
        db.execute("UPDATE security_users SET active=0 WHERE user_id='demo-approver'")
        count = db.execute('SELECT count(*) FROM security_sessions').fetchone()[0]
    monkeypatch.setattr(renew_demo_sessions, 'ROOT', tmp_path)
    target = tmp_path/'.private'/'renewed.json'
    with pytest.raises(ValueError):
        renew_demo_sessions.renew(target)
    assert not target.exists()
    with sqlite3.connect(tmp_path/'data.sqlite3') as db:
        assert db.execute('SELECT count(*) FROM security_sessions').fetchone()[0] == count
