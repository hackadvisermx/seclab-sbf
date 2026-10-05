import pathlib
import tempfile
import unittest
from unittest.mock import patch


class TestDashboardProjectDeletion(unittest.TestCase):
    def setUp(self):
        from app.services.workspace_sync import WorkspaceSyncService
        from app.services import workspace_sync, recon_service
        self.workspace_module = workspace_sync
        self.recon_module = recon_service
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.workspace = WorkspaceSyncService(self.root / "workspace")

    def test_delete_each_type_preserves_project_with_same_name(self):
        for kind in ("engagement", "reto"):
            self.workspace.create_engagement("sample", kind)
        (self.workspace.ws_path / "retos/sample/evidence/finding.md").write_text("evidence")
        (self.workspace.ws_path / "retos/sample/loot/nested").mkdir()
        self.workspace.delete_engagement("sample", "reto")
        self.assertFalse((self.workspace.ws_path / "retos/sample").exists())
        self.assertTrue((self.workspace.ws_path / "engagements/sample/notes.md").exists())
        self.workspace.delete_engagement("sample", "engagement")
        self.assertEqual(self.workspace.list_engagements(), [])
        self.workspace.create_engagement("-sample")
        self.workspace.delete_engagement("-sample")
        self.assertFalse((self.workspace.ws_path / "engagements/-sample").exists())
        with self.assertRaises(FileNotFoundError):
            self.workspace.delete_engagement("sample", "engagement")

    def test_invalid_paths_and_types_do_not_remove_workspace(self):
        self.workspace.create_engagement("sample")
        for name in ("", ".", "..", "../sample", "/tmp", "sample/..", "_plantilla", ".hidden"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.workspace.delete_engagement(name)
        with self.assertRaises(ValueError):
            self.workspace.delete_engagement("sample", "invalid")
        self.assertTrue((self.workspace.ws_path / "engagements/sample").is_dir())

    def test_symlinks_never_delete_external_files(self):
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "keep.txt").write_text("keep")
        projects = self.workspace.ws_path / "engagements"
        (projects / "linked").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.workspace.delete_engagement("linked")
        (projects / "linked").unlink()
        projects.rmdir()
        projects.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.workspace.delete_engagement("keep")
        self.assertEqual((outside / "keep.txt").read_text(), "keep")

    def test_running_recon_blocks_deletion_and_types_are_isolated(self):
        recon = self.recon_module.ReconService()
        self.workspace.create_engagement("sample", "engagement")
        self.workspace.create_engagement("sample", "reto")
        recon._jobs[("engagement", "sample")] = {"status": "running"}
        recon._jobs[("reto", "sample")] = {"status": "completed"}
        with patch.object(self.workspace_module, "workspace_service", self.workspace):
            with self.assertRaises(RuntimeError):
                recon.delete_engagement("sample", "engagement")
            self.assertTrue((self.workspace.ws_path / "engagements/sample").is_dir())
            recon.delete_engagement("sample", "reto")
            self.assertNotIn(("reto", "sample"), recon._jobs)
            self.assertIn(("engagement", "sample"), recon._jobs)

    def test_delete_api_success_missing_invalid_and_running(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api.endpoints import engagements
        app = FastAPI()
        app.include_router(engagements.router)
        recon = self.recon_module.ReconService()
        self.workspace.create_engagement("sample", "reto")
        self.workspace.create_engagement("sample", "engagement")
        with patch.object(self.workspace_module, "workspace_service", self.workspace), \
             patch.object(engagements, "recon_service", recon), TestClient(app) as client:
            invalid = client.delete("/engagements/sample?type=unknown")
            self.assertEqual(invalid.status_code, 400)
            recon._jobs[("reto", "sample")] = {"status": "running"}
            self.assertEqual(client.delete("/engagements/sample?type=reto").status_code, 409)
            self.assertTrue((self.workspace.ws_path / "retos/sample").exists())
            recon._jobs[("reto", "sample")]["status"] = "completed"
            deleted = client.delete("/engagements/sample?type=reto")
            self.assertEqual(deleted.status_code, 200)
            self.assertEqual(deleted.json()["type"], "reto")
            self.assertEqual(client.delete("/engagements/sample?type=reto").status_code, 404)
            self.assertTrue((self.workspace.ws_path / "engagements/sample").exists())


if __name__ == "__main__":
    unittest.main()
