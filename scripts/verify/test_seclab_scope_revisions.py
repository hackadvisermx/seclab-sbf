#!/usr/bin/env python3
"""Pruebas unitarias para el historial de revisiones y diffs de target.yaml (Phase 233 / V3-01h)."""

import pathlib
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from seclab_scope import record_scope_revision, get_scope_revisions


class TestScopeRevisions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.eng_dir = pathlib.Path(self.tmp.name) / "test-eng"
        self.eng_dir.mkdir(parents=True, exist_ok=True)

    def test_record_scope_creation_revision(self):
        new_yaml = """engagement:
  id: test-eng
authorization:
  allow_passive: true
scope:
  in_scope:
    domains:
      - target.local
"""
        rev = record_scope_revision(self.eng_dir, new_yaml)
        self.assertEqual(rev["action"], "created")
        self.assertIsNone(rev["previous_sha256"])
        self.assertIsNotNone(rev["new_sha256"])
        self.assertIn("target.local", rev["diff"])

        (self.eng_dir / "target.yaml").write_text(new_yaml, encoding="utf-8")

        # Second revision (update)
        updated_yaml = """engagement:
  id: test-eng
authorization:
  allow_passive: true
  allow_active: true
scope:
  in_scope:
    domains:
      - target.local
      - api.target.local
"""
        rev2 = record_scope_revision(self.eng_dir, updated_yaml)
        self.assertEqual(rev2["action"], "updated")
        self.assertEqual(rev2["previous_sha256"], rev["new_sha256"])
        self.assertIn("+      - api.target.local", rev2["diff"])
        self.assertIn("+  allow_active: true", rev2["diff"])

        # Fetch revisions
        history = get_scope_revisions(self.eng_dir)
        self.assertEqual(len(history), 2)
        # Newest first
        self.assertEqual(history[0]["revision_id"], rev2["revision_id"])
        self.assertEqual(history[1]["revision_id"], rev["revision_id"])

    def test_get_scope_revisions_empty(self):
        history = get_scope_revisions(self.eng_dir)
        self.assertEqual(history, [])


if __name__ == "__main__":
    unittest.main()
