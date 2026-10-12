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

    def test_verify_artifact_manifest_directory_success(self):
        deliverables_dir = self.eng_dir / "deliverables"
        deliverables_dir.mkdir()
        zip_output = deliverables_dir / "test-eng-pack.zip"
        pt_packer.pack_engagement(self.eng_dir, output_path=zip_output, sanitize=True, archive_format="zip")

        import zipfile
        with zipfile.ZipFile(zip_output, "r") as zf:
            m_bytes = zf.read("test-eng/artifact-manifest.json")
            (self.eng_dir / "artifact-manifest.json").write_bytes(m_bytes)

        res = pt_packer.verify_artifact_manifest(self.eng_dir)
        self.assertTrue(res["is_valid"])
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["corrupted_count"], 0)
        self.assertEqual(res["missing_count"], 0)
        self.assertGreater(res["verified_count"], 0)
        self.assertEqual(res["total_artifacts"], res["verified_count"])

    def test_verify_artifact_manifest_archive_zip_success(self):
        deliverables_dir = self.eng_dir / "deliverables"
        deliverables_dir.mkdir()
        zip_output = deliverables_dir / "bundle.zip"
        pt_packer.pack_engagement(self.eng_dir, output_path=zip_output, sanitize=True, archive_format="zip")

        res = pt_packer.verify_artifact_manifest(zip_output)
        self.assertTrue(res["is_valid"])
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["corrupted_count"], 0)
        self.assertEqual(res["missing_count"], 0)
        self.assertGreater(res["verified_count"], 0)

    def test_verify_artifact_manifest_archive_tar_success(self):
        deliverables_dir = self.eng_dir / "deliverables"
        deliverables_dir.mkdir()
        tar_output = deliverables_dir / "bundle.tar.gz"
        pt_packer.pack_engagement(self.eng_dir, output_path=tar_output, sanitize=True, archive_format="tar.gz")

        res = pt_packer.verify_artifact_manifest(tar_output)
        self.assertTrue(res["is_valid"])
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["corrupted_count"], 0)
        self.assertEqual(res["missing_count"], 0)
        self.assertGreater(res["verified_count"], 0)

    def test_verify_artifact_manifest_detects_hash_mismatch(self):
        deliverables_dir = self.eng_dir / "deliverables"
        deliverables_dir.mkdir()
        zip_output = deliverables_dir / "test-eng-pack.zip"
        pt_packer.pack_engagement(self.eng_dir, output_path=zip_output, sanitize=True, archive_format="zip")

        import zipfile
        with zipfile.ZipFile(zip_output, "r") as zf:
            m_bytes = zf.read("test-eng/artifact-manifest.json")
            (self.eng_dir / "artifact-manifest.json").write_bytes(m_bytes)

        # Alterar un archivo verificado
        (self.eng_dir / "notes.md").write_text("CONTENIDO ADULTERADO DESPUES DEL MANIFIESTO\n")

        res = pt_packer.verify_artifact_manifest(self.eng_dir)
        self.assertFalse(res["is_valid"])
        self.assertEqual(res["status"], "integrity_failed")
        self.assertEqual(res["corrupted_count"], 1)

        mismatches = [d for d in res["details"] if d["status"] == "hash_mismatch"]
        self.assertEqual(len(mismatches), 1)
        self.assertEqual(mismatches[0]["path"], "notes.md")

    def test_verify_artifact_manifest_detects_missing_file(self):
        deliverables_dir = self.eng_dir / "deliverables"
        deliverables_dir.mkdir()
        zip_output = deliverables_dir / "test-eng-pack.zip"
        pt_packer.pack_engagement(self.eng_dir, output_path=zip_output, sanitize=True, archive_format="zip")

        import zipfile
        with zipfile.ZipFile(zip_output, "r") as zf:
            m_bytes = zf.read("test-eng/artifact-manifest.json")
            (self.eng_dir / "artifact-manifest.json").write_bytes(m_bytes)

        # Borrar un archivo
        (self.eng_dir / "notes.md").unlink()

        res = pt_packer.verify_artifact_manifest(self.eng_dir)
        self.assertFalse(res["is_valid"])
        self.assertEqual(res["missing_count"], 1)

        missing = [d for d in res["details"] if d["status"] == "missing"]
        self.assertEqual(len(missing), 1)
        self.assertEqual(missing[0]["path"], "notes.md")

    def test_verify_artifact_manifest_rejects_symlinks(self):
        deliverables_dir = self.eng_dir / "deliverables"
        deliverables_dir.mkdir()
        zip_output = deliverables_dir / "test-eng-pack.zip"
        pt_packer.pack_engagement(self.eng_dir, output_path=zip_output, sanitize=True, archive_format="zip")

        import zipfile
        with zipfile.ZipFile(zip_output, "r") as zf:
            m_bytes = zf.read("test-eng/artifact-manifest.json")
            (self.eng_dir / "artifact-manifest.json").write_bytes(m_bytes)

        # Reemplazar archivo regular por symlink
        outside = pathlib.Path(self.tmp.name) / "outside.txt"
        outside.write_text("outside data")
        notes_path = self.eng_dir / "notes.md"
        notes_path.unlink()
        notes_path.symlink_to(outside)

        res = pt_packer.verify_artifact_manifest(self.eng_dir)
        self.assertFalse(res["is_valid"])
        sym_rejected = [d for d in res["details"] if d["status"] == "symlink_rejected"]
        self.assertEqual(len(sym_rejected), 1)

    def test_verify_artifact_manifest_rejects_unsafe_paths(self):
        mock_manifest = {
            "schema_version": 1,
            "engagement_id": "test-eng",
            "artifacts": [
                {"path": "../etc/shadow", "category": "other", "sha256": "abcdef"},
                {"path": "/etc/passwd", "category": "other", "sha256": "123456"},
            ]
        }
        res = pt_packer.verify_artifact_manifest(self.eng_dir, manifest_source=mock_manifest)
        self.assertFalse(res["is_valid"])
        self.assertEqual(res["corrupted_count"], 2)
        for d in res["details"]:
            self.assertEqual(d["status"], "rejected")

    def test_verify_artifact_manifest_invalid_schema(self):
        with self.assertRaises(ValueError):
            pt_packer.verify_artifact_manifest(self.eng_dir, manifest_source={"schema_version": 99})

    def test_verify_artifact_manifest_cli(self):
        deliverables_dir = self.eng_dir / "deliverables"
        deliverables_dir.mkdir()
        zip_output = deliverables_dir / "test-eng-pack.zip"
        pt_packer.pack_engagement(self.eng_dir, output_path=zip_output, sanitize=True, archive_format="zip")

        import zipfile
        with zipfile.ZipFile(zip_output, "r") as zf:
            m_bytes = zf.read("test-eng/artifact-manifest.json")
            (self.eng_dir / "artifact-manifest.json").write_bytes(m_bytes)

        import subprocess
        packer_script = REPO_ROOT / "scripts" / "pt-engagement-packer.py"
        proc = subprocess.run(
            [sys.executable, str(packer_script), "verify-manifest", str(self.eng_dir), "-j"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0)
        data = json.loads(proc.stdout)
        self.assertEqual(data.get("status"), "success")
        self.assertTrue(data.get("is_valid"))


if __name__ == "__main__":
    unittest.main()
