#!/usr/bin/env python3
"""Pruebas unitarias de seguridad para el redactor automático de secretos (seclab_redact)."""

import pathlib
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from seclab_redact import (
    redact_sensitive_text,
    parse_loot_credentials,
    REDACTED_API_KEY,
    REDACTED_TOKEN,
    REDACTED_PASSWORD,
    REDACTED_PRIVATE_KEY,
    REDACTED_HASH,
    REDACTED_CREDENTIAL,
)


class TestSeclabRedact(unittest.TestCase):
    def test_redact_api_keys(self):
        text = "Usa la clave sk-abc12345678901234567890123456 y AWS AKIAIOSFODNN7EXAMPLE para entrar."
        res = redact_sensitive_text(text)
        self.assertNotIn("sk-abc12345678901234567890123456", res["text"])
        self.assertNotIn("AKIAIOSFODNN7EXAMPLE", res["text"])
        self.assertIn(REDACTED_API_KEY, res["text"])
        self.assertGreaterEqual(res["replacements_count"], 2)
        self.assertIn("api_key", res["redacted_types"])

    def test_redact_bearer_token(self):
        text = "Authorization: Bearer mySecretToken1234567890abcdef123456 en la cabecera HTTP."
        res = redact_sensitive_text(text)
        self.assertNotIn("mySecretToken1234567890abcdef123456", res["text"])
        self.assertIn(REDACTED_TOKEN, res["text"])
        self.assertIn("bearer_token", res["redacted_types"])

    def test_redact_url_passwords(self):
        text = "Conectar a postgresql://dbuser:SuperSecretP@ss123@10.10.10.5:5432/production_db ahora."
        res = redact_sensitive_text(text)
        self.assertNotIn("SuperSecretP@ss123", res["text"])
        self.assertIn("postgresql://dbuser:", res["text"])
        self.assertIn(REDACTED_PASSWORD, res["text"])
        self.assertIn("@10.10.10.5", res["text"])
        self.assertIn("url_password", res["redacted_types"])

    def test_redact_pem_private_keys(self):
        text = (
            "Certificado recibido:\n"
            "-----BEGIN RSA PRIVATE KEY-----\n"
            "MIIEowIBAAKCAQEA0Y1+abcdefghijklmnopqrstuvwxyz1234567890==\n"
            "-----END RSA PRIVATE KEY-----\n"
            "Fin del archivo."
        )
        res = redact_sensitive_text(text)
        self.assertNotIn("MIIEowIBAAKCAQEA0Y1+abcdefghijklmnopqrstuvwxyz1234567890==", res["text"])
        self.assertIn(REDACTED_PRIVATE_KEY, res["text"])
        self.assertIn("private_key", res["redacted_types"])

    def test_redact_crypt_and_ntlm_hashes(self):
        text = (
            "Shadow file:\n"
            "root:$6$salt1234$abcdefghijklmnopqrstuvwxyz1234567890:19000:0:99999:7:::\n"
            "Hash NTLM hallado: password: e5922444e9ee6da47214361047251e2e en memoria."
        )
        res = redact_sensitive_text(text)
        self.assertNotIn("$6$salt1234$abcdefghijklmnopqrstuvwxyz1234567890", res["text"])
        self.assertNotIn("e5922444e9ee6da47214361047251e2e", res["text"])
        self.assertIn(REDACTED_HASH, res["text"])
        self.assertIn("password_hash", res["redacted_types"])

    def test_redact_loot_custom_terms(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = pathlib.Path(tmp_dir) / "credentials.csv"
            csv_path.write_text("username,password,service\nadmin,P@ssw0rdMegaSecret!,SSH\n")
            loot_terms = parse_loot_credentials(csv_path)

            text = "El operador usó P@ssw0rdMegaSecret! para iniciar sesión como admin."
            res = redact_sensitive_text(text, custom_terms=loot_terms)
            self.assertNotIn("P@ssw0rdMegaSecret!", res["text"])
            self.assertIn(REDACTED_CREDENTIAL, res["text"])
            self.assertIn("captured_credential", res["redacted_types"])


if __name__ == "__main__":
    unittest.main()
