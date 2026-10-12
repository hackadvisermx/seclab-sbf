#!/usr/bin/env python3
"""Detector y redactor automático de secretos y datos sensibles para SecLab-SBF.

Detecta y enmascara claves de API, contraseñas en URLs de conexión,
claves privadas PEM, hashes de contraseñas de formato estándar y
credenciales capturadas (loot) antes de enviar contexto al Copiloto LLM.

Sin dependencias externas obligatorias (Python 3 stdlib).
"""

import csv
import json
import os
import pathlib
import re
from typing import Any, Dict, List, Optional, Set, Tuple, Union

REDACTED_API_KEY = "[REDACTED_API_KEY]"
REDACTED_TOKEN = "[REDACTED_TOKEN]"
REDACTED_PASSWORD = "[REDACTED_PASSWORD]"
REDACTED_PRIVATE_KEY = "[REDACTED_PRIVATE_KEY]"
REDACTED_HASH = "[REDACTED_HASH]"
REDACTED_CREDENTIAL = "[REDACTED_CREDENTIAL]"

# Claves privadas PEM (RSA, EC, OPENSSH, etc.)
PEM_PRIVATE_KEY_PATTERN = re.compile(
    r"-----BEGIN (?:[A-Z0-9_-]+ )?PRIVATE KEY-----[\s\S]*?-----END (?:[A-Z0-9_-]+ )?PRIVATE KEY-----"
)

# Contraseñas en URLs / cadenas de conexión (http://user:pass@host, postgresql://user:pass@host, etc.)
URL_PASSWORD_PATTERN = re.compile(
    r"(?i)\b([a-z][a-z0-9+.-]*://(?:[^:\s/@]+)?:)([^@\s/]+)(@)"
)

# API keys de proveedores:
# AWS Access Key ID: AKIA... (20 caracteres alfanuméricos)
AWS_KEY_PATTERN = re.compile(r"\bAKIA[0-9A-Z]{16}\b")

# OpenAI / OpenRouter API keys: sk-... o sk-or-v1-...
OPENAI_OPENROUTER_KEY_PATTERN = re.compile(
    r"\bsk-(?:or-v1-[a-fA-F0-9]{32,}|[a-zA-Z0-9_-]{20,})\b"
)

# Tokens genéricos Bearer: Bearer <token>=20+ chars
BEARER_TOKEN_PATTERN = re.compile(
    r"(?i)\b(bearer\s+)([a-zA-Z0-9_\-\.]{20,})\b"
)

# Hashes de contraseñas de formato estándar (modular crypt: sha512crypt $6$, sha256crypt $5$, bcrypt $2b$/$2a$/$2y$, md5crypt $1$, argon2)
MODULAR_CRYPT_HASH_PATTERN = re.compile(
    r"\$(?:6|5|1|2a|2b|2y|argon2(?:id?|d))\$[a-zA-Z0-9./$,=+-]{16,}"
)

# Hashes NTLM/MD5 de 32 hex precedidos por hash, password, etc.
NTLM_MD5_KEYWORD_HASH_PATTERN = re.compile(
    r"(?i)\b((?:hash|password|passwd|pwd|ntlm|md5)\s*[:=]\s*)([a-fA-F0-9]{32})\b"
)

# Palabras reservadas que no deben redactarse si aparecen en archivos de botín como cabeceras
IGNORED_LOOT_TERMS = {
    "username", "user", "password", "pass", "hash", "service", "host",
    "port", "proto", "type", "description", "target", "notes", "id",
}


def parse_loot_credentials(source: Union[str, pathlib.Path]) -> List[str]:
    """Extrae términos sensibles (usuarios, contraseñas, hashes) de archivos de botín (CSV o JSON)."""
    terms: List[str] = []

    content = ""
    if isinstance(source, pathlib.Path) or (isinstance(source, str) and os.path.exists(source)):
        try:
            with open(source, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except OSError:
            return []
    elif isinstance(source, str):
        content = source

    if not content.strip():
        return []

    # Intentar formato JSON primero
    try:
        data = json.loads(content)
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    for key in ("username", "password", "hash", "token", "secret"):
                        val = item.get(key)
                        if isinstance(val, str) and len(val.strip()) >= 3:
                            terms.append(val.strip())
        elif isinstance(data, dict):
            creds = data.get("credentials", [])
            if isinstance(creds, list):
                for item in creds:
                    if isinstance(item, dict):
                        for key in ("username", "password", "hash", "token", "secret"):
                            val = item.get(key)
                            if isinstance(val, str) and len(val.strip()) >= 3:
                                terms.append(val.strip())
    except (json.JSONDecodeError, ValueError):
        # Intentar formato CSV
        try:
            reader = csv.reader(content.splitlines())
            for row in reader:
                for col in row:
                    clean = col.strip()
                    if clean and len(clean) >= 3 and clean.lower() not in IGNORED_LOOT_TERMS:
                        terms.append(clean)
        except Exception:
            pass

    # Deduplicar preservando orden
    seen: Set[str] = set()
    unique_terms: List[str] = []
    for t in terms:
        if t not in seen and t.lower() not in IGNORED_LOOT_TERMS:
            seen.add(t)
            unique_terms.append(t)
    return unique_terms


def redact_sensitive_text(
    text: str,
    custom_terms: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Detecta y enmascara patrones sensibles con sustituciones canónicas deterministas.

    Devuelve un diccionario con:
    - text: texto procesado con secretos enmascarados
    - replacements_count: cantidad total de reemplazos realizados
    - redacted_types: lista de tipos de datos enmascarados (sin duplicados)
    """
    if not text:
        return {
            "text": "" if text is not None else "",
            "replacements_count": 0,
            "redacted_types": [],
        }

    redacted = text
    total_count = 0
    types_found: List[str] = []

    # 1. Claves privadas PEM
    redacted, count = PEM_PRIVATE_KEY_PATTERN.subn(REDACTED_PRIVATE_KEY, redacted)
    if count > 0:
        total_count += count
        if "private_key" not in types_found:
            types_found.append("private_key")

    # 2. Contraseñas en URLs / cadenas de conexión
    redacted, count = URL_PASSWORD_PATTERN.subn(
        r"\g<1>" + REDACTED_PASSWORD + r"\g<3>",
        redacted,
    )
    if count > 0:
        total_count += count
        if "url_password" not in types_found:
            types_found.append("url_password")

    # 3. AWS Access Key IDs
    redacted, count = AWS_KEY_PATTERN.subn(REDACTED_API_KEY, redacted)
    if count > 0:
        total_count += count
        if "api_key" not in types_found:
            types_found.append("api_key")

    # 4. OpenAI / OpenRouter API keys
    redacted, count = OPENAI_OPENROUTER_KEY_PATTERN.subn(REDACTED_API_KEY, redacted)
    if count > 0:
        total_count += count
        if "api_key" not in types_found:
            types_found.append("api_key")

    # 5. Tokens Bearer
    redacted, count = BEARER_TOKEN_PATTERN.subn(
        r"\g<1>" + REDACTED_TOKEN,
        redacted,
    )
    if count > 0:
        total_count += count
        if "bearer_token" not in types_found:
            types_found.append("bearer_token")

    # 6. Hashes modular crypt (sha512crypt, bcrypt, sha256crypt, md5crypt, argon2)
    redacted, count = MODULAR_CRYPT_HASH_PATTERN.subn(REDACTED_HASH, redacted)
    if count > 0:
        total_count += count
        if "password_hash" not in types_found:
            types_found.append("password_hash")

    # 7. Hashes NTLM / MD5 precedidos de palabra clave
    redacted, count = NTLM_MD5_KEYWORD_HASH_PATTERN.subn(
        r"\g<1>" + REDACTED_HASH,
        redacted,
    )
    if count > 0:
        total_count += count
        if "password_hash" not in types_found:
            types_found.append("password_hash")

    # 8. Términos personalizados o credenciales de botín (loot)
    if custom_terms:
        # Ordenar por longitud descendente para evitar reemplazos de subcadenas parciales
        valid_terms = sorted(
            [t.strip() for t in custom_terms if isinstance(t, str) and len(t.strip()) >= 3],
            key=len,
            reverse=True,
        )
        for term in valid_terms:
            if term.lower() in IGNORED_LOOT_TERMS:
                continue
            prefix = r"\b" if term[0].isalnum() or term[0] == "_" else r""
            suffix = r"\b" if term[-1].isalnum() or term[-1] == "_" else r""
            pattern = re.compile(prefix + re.escape(term) + suffix)
            redacted, count = pattern.subn(REDACTED_CREDENTIAL, redacted)
            if count > 0:
                total_count += count
                if "captured_credential" not in types_found:
                    types_found.append("captured_credential")

    return {
        "text": redacted,
        "replacements_count": total_count,
        "redacted_types": types_found,
    }


def redact_context_file(
    text: str,
    loot_file: Optional[Union[str, pathlib.Path]] = None,
    custom_terms: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Aplica redacción incorporando automáticamente términos de un archivo de botín si existe."""
    terms = list(custom_terms or [])
    if loot_file:
        loot_path = pathlib.Path(loot_file)
        if loot_path.exists() and loot_path.is_file():
            terms.extend(parse_loot_credentials(loot_path))
    return redact_sensitive_text(text, custom_terms=terms)
