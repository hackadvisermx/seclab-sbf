import hashlib
import os
import pathlib
import tempfile
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.core import artifact_snapshot as snapshot
from app.api.endpoints import auth, loot
from app.main import app
from app.services.workspace_sync import WorkspaceSyncService


class TestArtifactSnapshot(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.service = WorkspaceSyncService(pathlib.Path(temporary.name))
        self.service.create_engagement('fixture')
        self.root = self.service._resolve_dir('fixture')
        self.path = self.root / 'recon/raw.txt'

    def test_fingerprint_matches_raw_bytes_and_refresh_changes_version_without_writing(self):
        for raw in (b'', 'Resultado original: á\n'.encode(), b'non-utf8: \xff', b'\0binary'):
            self.path.write_bytes(raw)
            before = self.path.stat()
            result = self.service.get_artifact_content('fixture', 'recon/raw.txt')
            self.assertEqual(result['sha256'], hashlib.sha256(raw).hexdigest())
            self.assertEqual(result['size'], len(raw))
            self.assertTrue(result['modified'].endswith('+00:00'))
            self.assertEqual(result['fingerprint_status'], 'available')
            expected = 'binary' if b'\0' in raw else 'decoded_with_replacement' if b'\xff' in raw else 'complete'
            self.assertEqual(result['preview_status'], expected)
            self.assertEqual(self.path.read_bytes(), raw)
            self.assertEqual(self.path.stat().st_mtime_ns, before.st_mtime_ns)
        self.assertEqual(sorted(p.name for p in self.path.parent.iterdir()), ['raw.txt'])

    def test_limits_hash_full_large_file_without_claiming_preview_and_skip_oversize(self):
        self.path.write_bytes(b'a' * (snapshot.PREVIEW_LIMIT + 1))
        result = self.service.get_artifact_content('fixture', 'recon/raw.txt')
        self.assertEqual(result['sha256'], hashlib.sha256(self.path.read_bytes()).hexdigest())
        self.assertEqual(result['preview_status'], 'too_large')
        with self.path.open('wb') as output:
            output.truncate(snapshot.HASH_LIMIT + 1)
        with patch.object(snapshot.os, 'read', side_effect=AssertionError('oversize must not read')):
            result = self.service.get_artifact_content('fixture', 'recon/raw.txt')
        self.assertIsNone(result['sha256'])
        self.assertEqual(result['fingerprint_status'], 'too_large')

    def test_rejects_paths_symlinks_and_special_files_without_blocking(self):
        self.path.write_text('fixture')
        for path in ('', '../raw.txt', '/etc/passwd', 'recon/../raw.txt', 'recon//raw.txt', 'recon/./raw.txt', 'recon'):
            with self.subTest(path=path), self.assertRaises(FileNotFoundError):
                snapshot.read_artifact_snapshot(self.root, path)
        linked = self.root / 'linked'
        linked.symlink_to(self.root / 'recon', target_is_directory=True)
        with self.assertRaises(FileNotFoundError):
            snapshot.read_artifact_snapshot(self.root, 'linked/raw.txt')
        linked.unlink()
        linked.symlink_to(self.path)
        with self.assertRaises(FileNotFoundError):
            snapshot.read_artifact_snapshot(self.root, 'linked')
        linked.unlink()
        os.mkfifo(linked)
        with self.assertRaises(FileNotFoundError):
            snapshot.read_artifact_snapshot(self.root, 'linked')

    def test_mutation_or_atomic_replacement_during_read_rejects_snapshot(self):
        real_read = os.read
        for replacement in (False, True):
            self.path.write_text('original')
            mutated = False
            def read_and_change(fd, count):
                nonlocal mutated
                value = real_read(fd, count)
                if not mutated:
                    mutated = True
                    if replacement:
                        temporary = self.path.with_suffix('.tmp')
                        temporary.write_text('replacement')
                        temporary.replace(self.path)
                    else:
                        self.path.write_text('changed and longer')
                return value
            with patch.object(snapshot.os, 'read', side_effect=read_and_change), self.assertRaises(snapshot.ArtifactChangedError):
                snapshot.read_artifact_snapshot(self.root, 'recon/raw.txt')

    def test_api_snapshot_and_changed_read_conflict_keep_authentication(self):
        self.path.write_text('fixture')
        client = TestClient(app)
        self.addCleanup(client.close)
        app.dependency_overrides[auth.require_operator] = lambda: 'fixture-only'
        try:
            with patch.object(loot, 'workspace_service', self.service):
                response = client.get('/api/v1/loot/fixture/artifacts/content', params={'path': 'recon/raw.txt'})
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()['sha256'], hashlib.sha256(b'fixture').hexdigest())
                with patch.object(self.service, 'get_artifact_content', side_effect=snapshot.ArtifactChangedError('Vuelve a seleccionar')):
                    self.assertEqual(client.get('/api/v1/loot/fixture/artifacts/content', params={'path': 'recon/raw.txt'}).status_code, 409)
        finally:
            app.dependency_overrides.pop(auth.require_operator, None)
        self.assertEqual(client.get('/api/v1/loot/fixture/artifacts/content', params={'path': 'recon/raw.txt'}).status_code, 401)
