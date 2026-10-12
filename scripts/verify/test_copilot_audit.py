#!/usr/bin/env python3
"""Pruebas unitarias para el registro de auditoría de consentimiento del Copiloto (Phase 227)."""

import hashlib
import json
import pathlib
import sys
import tempfile
import unittest

# Incluir scripts/ en sys.path
SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from seclab_copilot_audit import log_copilot_consent, read_copilot_consent_history


class TestCopilotConsentAudit(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.evidence_dir = pathlib.Path(self.temp_dir.name) / "evidence"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_log_copilot_consent_creates_jsonl_record(self):
        prompt = "¿Cuál es el vector de ataque?"
        context = "target.local scope data"
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        context_hash = hashlib.sha256(context.encode("utf-8")).hexdigest()

        record = log_copilot_consent(
            evidence_dir=self.evidence_dir,
            engagement_id="test-eng-1",
            agent_id="triage-agent",
            provider="openrouter",
            model="anthropic/claude-3.5-sonnet",
            network_tier="PUBLIC_REMOTE",
            prompt_hash=prompt_hash,
            context_hash=context_hash,
            context_bytes=len(context.encode("utf-8")),
            token="review-token-123",
        )

        self.assertEqual(record["engagement_id"], "test-eng-1")
        self.assertEqual(record["status"], "consented")
        self.assertEqual(record["network_tier"], "PUBLIC_REMOTE")
        self.assertEqual(record["prompt_hash"], prompt_hash)

        # Verificar archivo en disco
        consent_file = self.evidence_dir / ".copilot_consent.jsonl"
        self.assertTrue(consent_file.is_file())

        with open(consent_file, "r", encoding="utf-8") as f:
            lines = [json.loads(line) for line in f if line.strip()]

        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]["token"], "review-token-123")

    def test_read_copilot_consent_history_order_and_limit(self):
        # Registrar múltiples consentimientos
        for i in range(5):
            log_copilot_consent(
                evidence_dir=self.evidence_dir,
                engagement_id="test-eng-1",
                agent_id=f"agent-{i}",
                provider="local",
                model="llama3",
                network_tier="LOCAL_LOOPBACK",
                prompt_hash=f"hash-{i}",
                context_hash=f"ctx-hash-{i}",
                context_bytes=100 + i,
                token=f"token-{i}",
            )

        history = read_copilot_consent_history(self.evidence_dir, limit=3)
        self.assertEqual(len(history), 3)
        # El más reciente (token-4) debe ser el primero
        self.assertEqual(history[0]["token"], "token-4")
        self.assertEqual(history[1]["token"], "token-3")
        self.assertEqual(history[2]["token"], "token-2")

    def test_read_empty_history(self):
        history = read_copilot_consent_history(self.evidence_dir)
        self.assertEqual(history, [])


if __name__ == "__main__":
    unittest.main()
