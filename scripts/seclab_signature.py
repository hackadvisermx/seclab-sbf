#!/usr/bin/env python3
"""Módulo de Firma Criptográfica y Sellado de No Repudio de Artefactos (V3-03ee).

Genera y verifica firmas criptográficas de integridad y no repudio para
`artifact-manifest.json` y paquetes de auditoría en SecLab-SBF.
Utiliza HMAC-SHA256 con claves simétricas locales protegidas (modo 0600)
o claves maestras de auditoría.
"""

from __future__ import annotations

import datetime
import hashlib
import hmac
import json
import os
import pathlib
import secrets
from typing import Any, Dict, Optional, Tuple, Union


SIGNING_KEY_FILENAME = ".audit_signing_key"


def get_or_create_signing_key(engagement_dir: Union[str, pathlib.Path]) -> str:
    """Obtiene la clave de firma del engagement o genera una nueva de 256 bits."""
    eng_path = pathlib.Path(engagement_dir).resolve()
    key_file = eng_path / ".credentials" / SIGNING_KEY_FILENAME
    if not key_file.is_file():
        # Fallback a directorio raíz del engagement si .credentials no existe
        root_key_file = eng_path / SIGNING_KEY_FILENAME
        if root_key_file.is_file():
            key_file = root_key_file
        else:
            # Crear directorio .credentials si no existe
            creds_dir = eng_path / ".credentials"
            try:
                creds_dir.mkdir(parents=True, exist_ok=True)
            except Exception:
                creds_dir = eng_path
                key_file = creds_dir / SIGNING_KEY_FILENAME

            new_key = secrets.token_hex(32)
            try:
                # Escribir con permisos restrictivos (0600)
                fd = os.open(key_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(new_key.strip() + "\n")
            except Exception:
                key_file.write_text(new_key.strip() + "\n", encoding="utf-8")
            return new_key

    return key_file.read_text(encoding="utf-8").strip()


def sign_artifact_manifest(
    engagement_dir: Union[str, pathlib.Path],
    signer: str = "Lead Auditor",
    custom_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Firma criptográficamente el artifact-manifest.json de un engagement.
    
    Genera `artifact-manifest.sig.json` con el sello HMAC-SHA256, metadatos
    del firmante, timestamp UTC e identificador de clave.
    """
    eng_path = pathlib.Path(engagement_dir).resolve()
    manifest_path = eng_path / "artifact-manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"No se encontró artifact-manifest.json en {eng_path}")

    manifest_bytes = manifest_path.read_bytes()
    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()

    key = custom_key or get_or_create_signing_key(eng_path)
    sig_hex = hmac.new(
        key.encode("utf-8"),
        manifest_sha256.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    key_id = hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    signature_record: Dict[str, Any] = {
        "schema_version": 1,
        "algorithm": "HMAC-SHA256",
        "manifest_hash": manifest_sha256,
        "signer": signer.strip() if signer else "Lead Auditor",
        "signed_at": now_iso,
        "signature": sig_hex,
        "key_id": key_id,
    }

    sig_file = eng_path / "artifact-manifest.sig.json"
    # Escritura atómica
    tmp_sig = eng_path / f".tmp_{secrets.token_hex(4)}_artifact-manifest.sig.json"
    tmp_sig.write_text(json.dumps(signature_record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp_sig.replace(sig_file)

    return signature_record


def verify_manifest_signature(
    engagement_dir: Union[str, pathlib.Path],
    custom_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Verifica la validez y no repudio de la firma de artifact-manifest.json."""
    eng_path = pathlib.Path(engagement_dir).resolve()
    manifest_path = eng_path / "artifact-manifest.json"
    sig_path = eng_path / "artifact-manifest.sig.json"

    if not sig_path.is_file():
        return {
            "is_signed": False,
            "valid": False,
            "status": "unsigned",
            "message": "El engagement no cuenta con firma criptográfica de manifiesto.",
            "signature": None,
        }

    if not manifest_path.is_file():
        return {
            "is_signed": True,
            "valid": False,
            "status": "missing_manifest",
            "message": "Falta artifact-manifest.json pero existe la firma.",
            "signature": None,
        }

    try:
        sig_data = json.loads(sig_path.read_text(encoding="utf-8"))
    except Exception as e:
        return {
            "is_signed": True,
            "valid": False,
            "status": "corrupt_signature",
            "message": f"Archivo de firma corrupto: {e}",
            "signature": None,
        }

    manifest_bytes = manifest_path.read_bytes()
    current_manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    expected_hash = sig_data.get("manifest_hash")

    if current_manifest_sha256 != expected_hash:
        return {
            "is_signed": True,
            "valid": False,
            "status": "tampered_manifest",
            "message": "El contenido de artifact-manifest.json fue alterado tras su firma.",
            "current_hash": current_manifest_sha256,
            "signed_hash": expected_hash,
            "signature": sig_data,
        }

    key = custom_key or get_or_create_signing_key(eng_path)
    expected_sig = hmac.new(
        key.encode("utf-8"),
        expected_hash.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    provided_sig = sig_data.get("signature", "")
    if not hmac.compare_digest(provided_sig, expected_sig):
        return {
            "is_signed": True,
            "valid": False,
            "status": "invalid_key",
            "message": "La firma criptográfica no coincide con la clave de auditoría registrada.",
            "signature": sig_data,
        }

    return {
        "is_signed": True,
        "valid": True,
        "status": "verified",
        "message": "Firma criptográfica de manifiesto válida y verificada.",
        "signature": sig_data,
    }
