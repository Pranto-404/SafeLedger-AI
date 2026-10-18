"""The native adapter must retain the identity used by existing Render audits."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("key", ["12" * 16, "34" * 32])
def test_existing_signing_identity_is_preserved(key):
    script = """
import json, os
from api.app.security import signature
original = os.environ['SAFELEDGER_SIGNING_KEY']
# This is the effective identity of the already-running Render service.
os.environ['SAFELEDGER_SIGNING_KEY'] = original * 2 if len(original) == 32 else original
before = signature('migration-check', {'amount_minor': 101, 'business_id': 'test'})
os.environ['SAFELEDGER_SIGNING_KEY'] = original
from api.vercel import app
after = signature('migration-check', {'amount_minor': 101, 'business_id': 'test'})
print(json.dumps({'same_identity': before == after, 'last_route': app.routes[-1].name}))
"""
    result = subprocess.check_output([sys.executable, "-c", script], cwd=ROOT,
        env={**os.environ, "SAFELEDGER_SIGNING_KEY": key}, text=True)
    assert json.loads(result) == {"same_identity": True, "last_route": "frontend"}


@pytest.mark.parametrize("key", ["", "invalid-key"])
def test_adapter_does_not_invent_a_signing_identity(key):
    script = """
import os
before = os.environ['SAFELEDGER_SIGNING_KEY']
from api.vercel import app
assert os.environ['SAFELEDGER_SIGNING_KEY'] == before
from api.app.security import signature, PolicyError
try:
    signature('migration-check', {})
except PolicyError as error:
    assert error.code == 'SIGNING_KEY_NOT_CONFIGURED'
else:
    raise AssertionError('Invalid identity accepted')
"""
    subprocess.check_call([sys.executable, "-c", script], cwd=ROOT,
        env={**os.environ, "SAFELEDGER_SIGNING_KEY": key})
