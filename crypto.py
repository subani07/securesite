import os
import base64
import hmac
import hashlib
import bcrypt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

KEY_DIR = os.path.dirname(os.path.abspath(__file__))
MASTER_KEY_FILE = os.path.join(KEY_DIR, 'master.key')
HMAC_KEY_FILE = os.path.join(KEY_DIR, 'hmac.key')

def load_or_create_key(filepath, size=32):
    """Load an existing key or create one if it doesn't exist."""
    if os.path.exists(filepath):
        with open(filepath, 'rb') as f:
            return f.read()
    else:
        key = os.urandom(size)
        with open(filepath, 'wb') as f:
            f.write(key)
        return key

# Load keys
MASTER_KEY = load_or_create_key(MASTER_KEY_FILE)
HMAC_KEY = load_or_create_key(HMAC_KEY_FILE)

# --- Password Hashing (Bcrypt) ---
def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(password: str, hashed_password: str) -> bool:
    """Verify password against its bcrypt hash."""
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False

# --- Field-Level AES-256-GCM Encryption ---
def encrypt_data(plaintext: str) -> str:
    """Encrypt plaintext using AES-256-GCM and return base64 encoded string (nonce + ciphertext)."""
    if not plaintext:
        return ""
    aesgcm = AESGCM(MASTER_KEY)
    nonce = os.urandom(12)  # GCM recommended nonce size is 12 bytes
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode('utf-8'), None)
    # Combine nonce and ciphertext
    combined = nonce + ciphertext
    return base64.b64encode(combined).decode('utf-8')

def decrypt_data(ciphertext_b64: str) -> str:
    """Decrypt a base64 encoded AES-256-GCM string."""
    if not ciphertext_b64:
        return ""
    try:
        combined = base64.b64decode(ciphertext_b64.encode('utf-8'))
        if len(combined) < 12:
            return "[Decryption Error: Data Corrupted]"
        nonce = combined[:12]
        ciphertext = combined[12:]
        aesgcm = AESGCM(MASTER_KEY)
        plaintext_bytes = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext_bytes.decode('utf-8')
    except Exception as e:
        return f"[Decryption Error: {str(e)}]"

# --- Audit Log Integrity (HMAC-SHA256) ---
def generate_log_signature(timestamp: str, user_id: str, action: str, details: str, ip_address: str) -> str:
    """Generate a HMAC-SHA256 signature for a specific log entry to guarantee its integrity."""
    log_content = f"{timestamp}|{user_id}|{action}|{details}|{ip_address}"
    signature = hmac.new(HMAC_KEY, log_content.encode('utf-8'), hashlib.sha256)
    return signature.hexdigest()

def verify_log_entry(log_row) -> bool:
    """Verify the integrity signature of a single database log row."""
    # log_row can be a dictionary or a sqlite3.Row containing fields: timestamp, user_id, action, details, ip_address, hmac_signature
    try:
        user_id_str = str(log_row['user_id']) if log_row['user_id'] is not None else "None"
        expected_sig = generate_log_signature(
            timestamp=str(log_row['timestamp']),
            user_id=user_id_str,
            action=str(log_row['action']),
            details=str(log_row['details']),
            ip_address=str(log_row['ip_address'])
        )
        return hmac.compare_digest(expected_sig, str(log_row['hmac_signature']))
    except Exception:
        return False
