"""Trusted operator CLI: renew demo access without reseeding or changing authority.

Run on the backend host with its existing database and signing-key environment.
Credentials are written exclusively to an ignored private file, never stdout.
"""
import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import secrets
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from api.app import security as sec
from api.app.main import connect


def renew(destination, ttl_seconds=3600):
    destination = Path(destination).resolve()
    private_root = (ROOT / '.private').resolve()
    if not destination.is_relative_to(private_root):
        raise ValueError('Output must be inside the ignored .private directory')
    if not 1 <= ttl_seconds <= 86400:
        raise ValueError('Session lifetime must be between 1 and 86400 seconds')
    sec.signature('session-renewal', 'configuration-check')
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    destination.parent.chmod(0o700)
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'w') as output, closing(connect()) as db:
            tokens = {}
            with db:
                for role in ('owner', 'approver', 'viewer', 'agent'):
                    user_id = 'demo-' + role
                    row = db.execute('SELECT business_id,role,active FROM security_users WHERE user_id=?', (user_id,)).fetchone()
                    if row is None or tuple(row) != ('synthetic-demo', role, 1):
                        raise ValueError('Existing demo identity is missing, inactive or has changed; renewal stopped')
                    token = secrets.token_urlsafe(32)
                    db.execute('INSERT INTO security_sessions VALUES (?,?,?)',
                               (hashlib.sha256(token.encode()).hexdigest(), user_id, sec.now() + ttl_seconds))
                    tokens[role] = token
                json.dump({'simulation_only': True, 'expires_after_seconds': ttl_seconds, 'bearer_tokens': tokens}, output, indent=2)
                output.flush()
                os.fsync(output.fileno())
        print('Demo sessions renewed privately; data, roles and existing sessions preserved.')
    except BaseException:
        destination.unlink(missing_ok=True)
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, help='New file inside .private/')
    parser.add_argument('--ttl-seconds', type=int, default=3600)
    args = parser.parse_args()
    renew(args.output, args.ttl_seconds)
