import os
import base64
import hmac as _hmac
import hashlib
import secrets
from datetime import datetime, timedelta
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

KEY_DIR = os.path.dirname(os.path.abspath(__file__))
MASTER_KEY_FILE = os.path.join(os.path.dirname(KEY_DIR), 'master.key')
HMAC_KEY_FILE = os.path.join(os.path.dirname(KEY_DIR), 'hmac.key')


def load_or_create_key(filepath, size=32):
    """Load an existing binary key or create a new one."""
    if os.path.exists(filepath):
        with open(filepath, 'rb') as f:
            return f.read()
    key = os.urandom(size)
    with open(filepath, 'wb') as f:
        f.write(key)
    return key


MASTER_KEY = load_or_create_key(MASTER_KEY_FILE)
HMAC_KEY = load_or_create_key(HMAC_KEY_FILE)


# ── Password Hashing (via Flask-Bcrypt extension) ──────────────────────────────
def check_password_strength(password: str) -> dict:
    """Return a strength score and list of issues for a given password."""
    issues = []
    score = 0

    if len(password) >= 8:
        score += 1
    else:
        issues.append('At least 8 characters required')

    if len(password) >= 12:
        score += 1

    if any(c.isupper() for c in password):
        score += 1
    else:
        issues.append('At least one uppercase letter required')

    if any(c.islower() for c in password):
        score += 1
    else:
        issues.append('At least one lowercase letter required')

    if any(c.isdigit() for c in password):
        score += 1
    else:
        issues.append('At least one digit required')

    special = set('!@#$%^&*()_+-=[]{}|;:,.<>?')
    if any(c in special for c in password):
        score += 1
    else:
        issues.append('At least one special character required')

    labels = {1: 'Very Weak', 2: 'Weak', 3: 'Fair', 4: 'Good', 5: 'Strong', 6: 'Very Strong'}
    return {
        'score': score,
        'max_score': 6,
        'label': labels.get(score, 'Very Weak'),
        'issues': issues,
        'is_acceptable': score >= 3,
    }


# ── AES-256-GCM Field Encryption ───────────────────────────────────────────────
def encrypt_data(plaintext: str) -> str:
    if not plaintext:
        return ''
    aesgcm = AESGCM(MASTER_KEY)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode('utf-8'), None)
    return base64.b64encode(nonce + ciphertext).decode('utf-8')


def decrypt_data(ciphertext_b64: str) -> str:
    if not ciphertext_b64:
        return ''
    try:
        combined = base64.b64decode(ciphertext_b64.encode('utf-8'))
        nonce, ciphertext = combined[:12], combined[12:]
        aesgcm = AESGCM(MASTER_KEY)
        return aesgcm.decrypt(nonce, ciphertext, None).decode('utf-8')
    except Exception as e:
        return f'[Decryption Error: {e}]'


# ── Secure Token Generation (password reset, etc.) ─────────────────────────────
def generate_secure_token(length: int = 48) -> str:
    return secrets.token_urlsafe(length)


def generate_reset_token() -> tuple[str, datetime]:
    """Generate a time-limited password reset token."""
    token = generate_secure_token()
    expires = datetime.utcnow() + timedelta(hours=1)
    return token, expires


# ── HMAC Log Integrity ─────────────────────────────────────────────────────────
def generate_log_signature(timestamp, user_id, action, details, ip_address) -> str:
    content = f'{timestamp}|{user_id}|{action}|{details}|{ip_address}'
    sig = _hmac.new(HMAC_KEY, content.encode('utf-8'), hashlib.sha256)
    return sig.hexdigest()
