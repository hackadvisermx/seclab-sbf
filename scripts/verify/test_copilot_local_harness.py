#!/usr/bin/env python3
"""Pruebas unitarias para el harness de modelos locales (Ollama/vLLM) y fallback determinista (V3-05o)."""

import io
import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.seclab_copilot_harness import (
    generate_heuristic_fallback,
    normalize_provider_url,
    probe_local_provider,
)


class TestCopilotLocalHarness(unittest.TestCase):
    def test_normalize_provider_url(self):
        self.assertEqual(normalize_provider_url(None), "http://127.0.0.1:11434")
        self.assertEqual(normalize_provider_url(""), "http://127.0.0.1:11434")
        self.assertEqual(normalize_provider_url("127.0.0.1:8000"), "http://127.0.0.1:8000")
        self.assertEqual(normalize_provider_url("http://localhost:11434/"), "http://localhost:11434")
        self.assertEqual(normalize_provider_url("https://vllm.internal:8000/v1/"), "https://vllm.internal:8000/v1")

    @patch("urllib.request.urlopen")
    def test_probe_local_provider_ollama_online(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.getcode.return_value = 200
        mock_resp.read.return_value = json.dumps({
            "models": [
                {"name": "llama3:latest"},
                {"name": "mistral:instruct"},
            ]
        }).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        res = probe_local_provider("http://127.0.0.1:11434", timeout_seconds=1.0)
        self.assertEqual(res["status"], "ONLINE")
        self.assertEqual(res["provider_type"], "ollama")
        self.assertIn("llama3:latest", res["models"])
        self.assertIn("mistral:instruct", res["models"])
        self.assertIsNone(res["error"])

    @patch("urllib.request.urlopen")
    def test_probe_local_provider_vllm_online(self, mock_urlopen):
        # Primer intento /api/tags falla con 404, segundo intento /v1/models tiene exito
        resp_404 = urllib.error.HTTPError("http://127.0.0.1:8000/api/tags", 404, "Not Found", {}, None)
        mock_resp_vllm = MagicMock()
        mock_resp_vllm.getcode.return_value = 200
        mock_resp_vllm.read.return_value = json.dumps({
            "data": [
                {"id": "meta-llama/Meta-Llama-3-8B-Instruct"},
                {"id": "deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct"},
            ]
        }).encode("utf-8")
        mock_resp_vllm.__enter__.return_value = mock_resp_vllm

        mock_urlopen.side_effect = [resp_404, mock_resp_vllm]

        res = probe_local_provider("http://127.0.0.1:8000", timeout_seconds=1.0)
        self.assertEqual(res["status"], "ONLINE")
        self.assertEqual(res["provider_type"], "vllm_openai")
        self.assertIn("meta-llama/Meta-Llama-3-8B-Instruct", res["models"])
        self.assertIsNone(res["error"])

    @patch("urllib.request.urlopen")
    def test_probe_local_provider_offline_refused(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

        res = probe_local_provider("http://127.0.0.1:9999", timeout_seconds=0.5)
        self.assertEqual(res["status"], "OFFLINE")
        self.assertEqual(res["models"], [])
        self.assertIsNotNone(res["error"])
        self.assertIn("Connection refused", res["error"])

    def test_generate_heuristic_fallback_with_scope_and_evidence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tdir = pathlib.Path(tmpdir)
            target_yaml = tdir / "target.yaml"
            target_yaml.write_text(
                "in_scope:\n  - 'target.local'\n  - '192.168.1.50'\nout_of_scope:\n  - 'prod.target.local'\n",
                encoding="utf-8",
            )
            evidence_dir = tdir / "evidence"
            evidence_dir.mkdir()
            (evidence_dir / "sqli_login.md").write_text("# SQL Injection\n", encoding="utf-8")

            res_recon = generate_heuristic_fallback(
                engagement_dir=tdir,
                agent_id="recon-agent",
                user_message="¿Cómo inicio el reconocimiento del segmento interno?",
            )

            self.assertIn("ℹ️ [Modo Degradación Determinista Local", res_recon)
            self.assertIn("Orientación Táctica Local (Agente: `recon-agent`)", res_recon)
            self.assertIn("`target.local`", res_recon)
            self.assertIn("`prod.target.local`", res_recon)
            self.assertIn("sqli_login", res_recon)
            self.assertIn("Nota de Incertidumbre y Verificación", res_recon)
            self.assertIn("Enumeracion de Superficie", res_recon)

            res_auth = generate_heuristic_fallback(
                engagement_dir=tdir,
                agent_id="auth-agent",
                user_message="¿Qué pruebas aplico sobre el endpoint de cambio de contraseña?",
            )
            self.assertIn("Matriz de Control de Acceso", res_auth)
            self.assertIn("Vulnerabilidades BOLA/IDOR", res_auth)


if __name__ == "__main__":
    unittest.main()
