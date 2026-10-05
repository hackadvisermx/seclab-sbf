import base64
import hmac
import hashlib
import os
import pathlib
import time
from typing import Optional
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.config import VAULT_KEY_PATH, SECRET_KEY


def get_or_create_vault_key() -> bytes:
    """Obtiene o genera una clave simétrica AES-256 de 32 bytes para el vault cifrado."""
    if VAULT_KEY_PATH.exists():
        try:
            key_data = VAULT_KEY_PATH.read_bytes()
            if len(key_data) == 32:
                return key_data
        except Exception:
            pass

    # Generar nueva clave criptográfica
    new_key = AESGCM.generate_key(bit_length=256)
    try:
        VAULT_KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
        VAULT_KEY_PATH.write_bytes(new_key)
        os.chmod(VAULT_KEY_PATH, 0o600)
    except Exception:
        # Fallback determinista derivado de SECRET_KEY
        return hashlib.sha256(SECRET_KEY.encode()).digest()

    return new_key


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
    """Crea un token de sesión firmado para autenticación del dashboard."""
    expires_at = int(time.time()) + (86400 * 7) # 7 días
    msg = f"{username}:{expires_at}".encode()
    signature = hmac.new(SECRET_KEY.encode(), msg, hashlib.sha256).hexdigest()
    raw = f"{username}:{expires_at}:{signature}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def verify_session_token(token: str) -> Optional[str]:
    """Verifica la validez y expiración del token de sesión. Retorna el username o None."""
    try:
        raw = base64.urlsafe_b64decode(token.encode()).decode()
        username, expires_at_str, signature = raw.split(":", 2)
        expires_at = int(expires_at_str)
        if time.time() > expires_at:
            return None
        msg = f"{username}:{expires_at}".encode()
        expected = hmac.new(SECRET_KEY.encode(), msg, hashlib.sha256).hexdigest()
        if hmac.compare_digest(expected, signature):
            return username
    except Exception:
        return None
    return None
