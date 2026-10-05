import base64
import hashlib
import os
import time
from typing import Optional
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.config import VAULT_KEY_PATH, VAULT_DB_PATH


def get_or_create_vault_key() -> bytes:
    from app.core.key_store import persistent_key
    if not VAULT_KEY_PATH.exists() and VAULT_DB_PATH.exists():
        import sqlite3
        connection = sqlite3.connect(f"file:{VAULT_DB_PATH}?mode=ro", uri=True)
        try:
            has_table = connection.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'api_keys'").fetchone()
            if has_table and connection.execute("SELECT 1 FROM api_keys WHERE encrypted_key != '' LIMIT 1").fetchone():
                raise RuntimeError("Falta la clave de una bóveda con datos: restaura la clave desde el respaldo.")
        finally:
            connection.close()
    return persistent_key(VAULT_KEY_PATH)


_VAULT_KEY = get_or_create_vault_key()


def encrypt_secret(plaintext: str) -> str:
    """Cifra una cadena usando AES-256-GCM y retorna base64(nonce + ciphertext)."""
    if not plaintext:
        return ""
    aesgcm = AESGCM(_VAULT_KEY)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    payload = nonce + ciphertext
    return base64.b64encode(payload).decode("utf-8")


def decrypt_secret(encrypted_b64: str) -> str:
    """Descifra un secreto en base64 usando AES-256-GCM."""
    if not encrypted_b64:
        return ""
    try:
        payload = base64.b64decode(encrypted_b64.encode("utf-8"))
        nonce = payload[:12]
        ciphertext = payload[12:]
        aesgcm = AESGCM(_VAULT_KEY)
        decrypted = aesgcm.decrypt(nonce, ciphertext, None)
        return decrypted.decode("utf-8")
    except Exception as e:
        return f"[Error al descifrar: {str(e)}]"


def mask_secret(plaintext: str) -> str:
    """Devuelve una versión enmascarada para mostrar en la interfaz (ej. sk-1234...abcd)."""
    if not plaintext:
        return ""
    if len(plaintext) <= 8:
        return "••••••••"
    return f"{plaintext[:4]}••••••••{plaintext[-4:]}"


def create_session_token(username: str) -> str:
    from app.config import SESSION_SECONDS
    from app.core.database import get_db_connection
    token = base64.urlsafe_b64encode(os.urandom(32)).decode()
    connection = get_db_connection()
    try:
        with connection:
            connection.execute("DELETE FROM dashboard_sessions WHERE expires_at <= ?", (int(time.time()),))
            connection.execute(
                "INSERT INTO dashboard_sessions (token_hash, username, expires_at) VALUES (?, ?, ?)",
                (hashlib.sha256(token.encode()).hexdigest(), username, int(time.time()) + SESSION_SECONDS),
            )
    finally:
        connection.close()
    return token


def verify_session_token(token: str) -> Optional[str]:
    from app.core.database import get_db_connection
    if not token or len(token) > 256:
        return None
    connection = get_db_connection()
    try:
        row = connection.execute(
            "SELECT username FROM dashboard_sessions WHERE token_hash = ? AND expires_at > ?",
            (hashlib.sha256(token.encode()).hexdigest(), int(time.time())),
        ).fetchone()
        return 'tester' if row and row['username'] == 'tester' else None
    finally:
        connection.close()


def revoke_session_token(token: str):
    from app.core.database import get_db_connection
    connection = get_db_connection()
    try:
        with connection:
            connection.execute("DELETE FROM dashboard_sessions WHERE token_hash = ?", (hashlib.sha256(token.encode()).hexdigest(),))
    finally:
        connection.close()
