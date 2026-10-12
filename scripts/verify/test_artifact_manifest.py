#!/usr/bin/env python3
"""Pruebas unitarias de integridad para el manifiesto de artefactos (artifact-manifest v1)."""

import json
import pathlib
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import importlib.util

packer_spec = importlib.util.spec_from_file_location(
    "pt_engagement_packer",
    str(REPO_ROOT / "scripts" / "pt-engagement-packer.py"),
)
pt_packer = importlib.util.module_from_spec(packer_spec)
packer_spec.loader.exec_module(pt_packer)


class TestArtifactManifest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.eng_dir = pathlib.Path(self.tmp.name) / "test-eng"
        self.eng_dir.mkdir(parents=True, exist_ok=True)

        import shutil
        target_tmpl = REPO_ROOT / "workspace-seed" / "templates" / "target.yaml"
        shutil.copy(target_tmpl, self.eng_dir / "target.yaml")
        scope_tmpl = REPO_ROOT / "workspace-seed" / "templates" / "scope.txt"
        shutil.copy(scope_tmpl, self.eng_dir / "scope.txt")

        ev_dir = self.eng_dir / "evidence"
        ev_dir.mkdir()
        ev_tmpl = REPO_ROOT / "workspace-seed" / "templates" / "evidence.md"
        shutil.copy(ev_tmpl, ev_dir / "VULN-01.md")

        (self.eng_dir / "notes.md").write_text("Notas técnicas de prueba.\n")

        recon_dir = self.eng_dir / "recon"
        recon_dir.mkdir()
        (recon_dir / "live_hosts.txt").write_text("https://api.example.com\n")
        (recon_dir / "summary.json").write_text('{"engagement": "fixture"}\n')

    def tearDown(self):
        self.tmp.cleanup()

    def test_packer_generates_artifact_manifest(self):
        deliverables_dir = self.eng_dir / "deliverables"
        deliverables_dir.mkdir()
        zip_output = deliverables_dir / "test-eng-pack.zip"

        pt_packer.pack_engagement(
            self.eng_dir,
            output_path=zip_output,
            sanitize=True,
            archive_format="zip",
        )

        self.assertTrue(zip_output.is_file())

        import zipfile
        with zipfile.ZipFile(zip_output, "r") as zf:
            names = zf.namelist()
            manifest_name = "test-eng/artifact-manifest.json"
            self.assertIn(manifest_name, names)

            manifest_content = zf.read(manifest_name).decode("utf-8")
            data = json.loads(manifest_content)

            self.assertEqual(data.get("schema_version"), 1)
            self.assertEqual(data.get("engagement_id"), "test-eng")
            self.assertTrue(data.get("sanitized"))
            self.assertIn("artifacts", data)
            self.assertGreater(data.get("total_artifacts"), 0)
            self.assertGreater(data.get("total_bytes"), 0)

            categories = {item["category"] for item in data["artifacts"]}
            self.assertIn("report", categories)
            self.assertIn("scope", categories)
            self.assertIn("evidence", categories)
            self.assertIn("recon", categories)


if __name__ == "__main__":
    unittest.main()
