"""Time-based one-time passwords (RFC 6238, SHA-1, 6 digits, 30 s) with sealed secrets and one-use backup codes."""
import base64
import hashlib
import hmac
import os
import secrets
import struct
import time

STEP_SECONDS = 30
ALPHABET = 'abcdefghjkmnpqrstuvwxyz23456789'


def _key(label):
    signing = os.environ.get('SAFELEDGER_SIGNING_KEY', '')
    if len(signing) != 64:raise ValueError('Signing key not configured')
    return hmac.new(bytes.fromhex(signing), label, hashlib.sha256).digest()


def new_secret():
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip('=')


def _stream(key, nonce, length):
    out, counter = b'', 0
    while len(out) < length:
        out += hmac.new(key, nonce + counter.to_bytes(4, 'big'), hashlib.sha256).digest()
        counter += 1
    return out[:length]


def seal(secret):
    """Encrypt-then-MAC with a key derived from the server signing key; the database alone cannot reveal secrets."""
    key, nonce, plain = _key(b'safeledger-mfa-seal-v1'), secrets.token_bytes(12), secret.encode()
    cipher = bytes(a ^ b for a, b in zip(plain, _stream(key, nonce, len(plain))))
    tag = hmac.new(key, nonce + cipher, hashlib.sha256).digest()[:16]
    return (nonce + cipher + tag).hex()


def unseal(blob):
    raw = bytes.fromhex(blob)
    nonce, cipher, tag = raw[:12], raw[12:-16], raw[-16:]
    key = _key(b'safeledger-mfa-seal-v1')
    if not hmac.compare_digest(tag, hmac.new(key, nonce + cipher, hashlib.sha256).digest()[:16]):raise ValueError('Sealed secret failed verification')
    return bytes(a ^ b for a, b in zip(cipher, _stream(key, nonce, len(cipher)))).decode()


def code_at(secret, step):
    padded = secret + '=' * (-len(secret) % 8)
    digest = hmac.new(base64.b32decode(padded, casefold=True), struct.pack('>Q', step), hashlib.sha1).digest()
    offset = digest[-1] & 15
    return '%06d' % ((struct.unpack('>I', digest[offset:offset + 4])[0] & 0x7FFFFFFF) % 10**6)


def verify(secret, code, last_step=0, now=None):
    """Return the matched time step, or None. Accepts one step of clock drift; a step can be used only once."""
    code = ''.join(ch for ch in str(code) if ch.isdigit())
    if len(code) != 6:return None
    current = int((now if now is not None else time.time()) // STEP_SECONDS)
    for step in (current - 1, current, current + 1):
        if step > last_step and hmac.compare_digest(code_at(secret, step), code):return step
    return None


def provisioning_uri(secret, username):
    return f'otpauth://totp/Capzoryx%20Copilot:{username}?secret={secret}&issuer=Capzoryx%20Copilot&algorithm=SHA1&digits=6&period={STEP_SECONDS}'


def new_backup_codes(count=10):
    return [''.join(secrets.choice(ALPHABET) for _ in range(4)) + '-' + ''.join(secrets.choice(ALPHABET) for _ in range(4)) for _ in range(count)]


def hash_backup(code):
    normal = ''.join(ch for ch in code.lower() if ch.isalnum())
    return hmac.new(_key(b'safeledger-mfa-backup-v1'), normal.encode(), hashlib.sha256).hexdigest()
