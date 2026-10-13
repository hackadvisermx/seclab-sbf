#!/usr/bin/env python3
"""Pruebas unitarias para firma criptográfica de artefactos (scripts/seclab_signature.py)."""

import json
import pathlib
import tempfile
import unittest

from scripts.seclab_signature import (
    get_or_create_signing_key,
    sign_artifact_manifest,
    verify_manifest_signature,
)


class TestSeclabSignature(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.eng_dir = pathlib.Path(self.tmp_dir.name) / "test-eng"
        self.eng_dir.mkdir(parents=True, exist_ok=True)
        # Crear un artifact-manifest.json válido
        self.manifest_file = self.eng_dir / "artifact-manifest.json"
        self.manifest_data = {
            "schema_version": 1,
            "generated_at": "2026-10-12T19:00:00Z",
            "engagement_name": "test-eng",
            "total_artifacts": 1,
            "artifacts": [
                {
                    "path": "REPORT.md",
                    "category": "deliverables",
                    "sha256": "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
                    "size_bytes": 1024,
                }
            ],
        }
        self.manifest_file.write_text(json.dumps(self.manifest_data, indent=2), encoding="utf-8")

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_get_or_create_signing_key(self):
        key1 = get_or_create_signing_key(self.eng_dir)
        self.assertTrue(isinstance(key1, str) and len(key1) == 64)
        # Llamar de nuevo debe devolver la misma clave
        key2 = get_or_create_signing_key(self.eng_dir)
        self.assertEqual(key1, key2)

    def test_sign_artifact_manifest_success(self):
        res = sign_artifact_manifest(self.eng_dir, signer="SecLab Auditor")
        self.assertEqual(res["algorithm"], "HMAC-SHA256")
        self.assertEqual(res["signer"], "SecLab Auditor")
        self.assertTrue(len(res["signature"]) == 64)
        self.assertTrue((self.eng_dir / "artifact-manifest.sig.json").is_file())

    def test_verify_manifest_signature_valid(self):
        sign_artifact_manifest(self.eng_dir, signer="SecLab Auditor")
        ver = verify_manifest_signature(self.eng_dir)
        self.assertTrue(ver["is_signed"])
        self.assertTrue(ver["valid"])
        self.assertEqual(ver["status"], "verified")
        self.assertEqual(ver["signature"]["signer"], "SecLab Auditor")

    def test_verify_manifest_signature_tampered(self):
        sign_artifact_manifest(self.eng_dir, signer="SecLab Auditor")
        # Alterar el manifiesto
        self.manifest_file.write_text("{\"tampered\": true}", encoding="utf-8")
        ver = verify_manifest_signature(self.eng_dir)
        self.assertTrue(ver["is_signed"])
        self.assertFalse(ver["valid"])
        self.assertEqual(ver["status"], "tampered_manifest")

    def test_verify_manifest_signature_unsigned(self):
        ver = verify_manifest_signature(self.eng_dir)
        self.assertFalse(ver["is_signed"])
        self.assertFalse(ver["valid"])
        self.assertEqual(ver["status"], "unsigned")

    def test_verify_manifest_signature_invalid_key(self):
        sign_artifact_manifest(self.eng_dir, signer="SecLab Auditor", custom_key="key_11111111111111111111111111111111")
        # Verificar con otra clave
        ver = verify_manifest_signature(self.eng_dir, custom_key="key_22222222222222222222222222222222")
        self.assertTrue(ver["is_signed"])
        self.assertFalse(ver["valid"])
        self.assertEqual(ver["status"], "invalid_key")


if __name__ == "__main__":
    unittest.main()
