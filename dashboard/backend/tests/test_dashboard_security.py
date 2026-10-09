import os
import pathlib
import tempfile
import unittest
from unittest.mock import patch


class TestDashboardAuthentication(unittest.TestCase):
    def setUp(self):
        from app.main import app
        from app.api.endpoints import auth
        from app.core import database
        from fastapi.testclient import TestClient
        self.auth = auth
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db_patch = patch.object(database, 'VAULT_DB_PATH', pathlib.Path(self.temp.name) / 'test.db')
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)
        database.init_db()
        auth._attempts.clear()
        self.password_patch = patch.object(auth, 'TESTER_PASSWORD', 'fixture-password')
        self.password_patch.start()
        self.addCleanup(self.password_patch.stop)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def login(self):
        response = self.client.post('/api/v1/auth/login', json={'password': 'fixture-password'})
        self.assertEqual(response.status_code, 200, response.text)
        return response

    def test_lab_password_parser_preserves_literal_values_and_first_entry(self):
        from app.config import load_lab_settings
        path = pathlib.Path(self.temp.name) / 'lab.env'
        path.write_text("TTYD_PASSWORD= literal 'fixture' = value \nTTYD_PASSWORD=ignored\n")
        self.assertEqual(load_lab_settings(path)['TTYD_PASSWORD'], " literal 'fixture' = value ")

    def test_all_registered_api_routes_require_session(self):
        from app.main import app
        import re
        checked = 0
        for path, operations in app.openapi()['paths'].items():
            if not path.startswith('/api/v1') or path == '/api/v1/auth/login':
                continue
            url = re.sub(r'\{[^}]+\}', 'fixture', path)
            for method in operations:
                if method not in {'get', 'post', 'put', 'delete', 'patch'}:
                    continue
                with self.subTest(url=url, method=method):
                    response = self.client.request(method, url, json={})
                    self.assertEqual(response.status_code, 401, response.text)
                    checked += 1
        self.assertGreater(checked, 50)

    def test_cookie_session_and_logout_revocation(self):
        response = self.login()
        cookie = response.headers['set-cookie'].lower()
        self.assertIn('httponly', cookie)
        self.assertIn('samesite=strict', cookie)
        self.assertNotIn('token', response.json())
        token = self.client.cookies.get('seclab_session')
        self.assertEqual(self.client.get('/api/v1/vault').status_code, 200)
        self.assertEqual(self.client.post('/api/v1/auth/logout').status_code, 200)
        self.assertEqual(self.client.get('/api/v1/vault', headers={'Authorization': 'Bearer ' + token}).status_code, 401)

    def test_authenticated_report_preview_and_download(self):
        from app.services.workspace_sync import WorkspaceSyncService
        from app.api.endpoints import reports
        workspace = WorkspaceSyncService(pathlib.Path(self.temp.name) / 'workspace')
        workspace.create_engagement('fixture')
        project = workspace._resolve_dir('fixture')
        (project / 'REPORT.md').write_text('# Informe de prueba')
        (project / 'exports').mkdir()
        (project / 'exports/bundle.zip').write_bytes(b'fixture archive')
        self.login()
        with patch.object(reports, 'workspace_service', workspace):
            self.assertEqual(self.client.get('/api/v1/reports/fixture/preview').json()['content'], '# Informe de prueba')
            download = self.client.get('/api/v1/reports/fixture/download')
            self.assertEqual(download.status_code, 200)
            import io, tarfile
            self.assertNotEqual(download.content, b'fixture archive')
            with tarfile.open(fileobj=io.BytesIO(download.content)) as archive:
                self.assertIn('fixture/REPORT.md', archive.getnames())
            self.assertEqual(download.headers['cache-control'], 'no-store')

    def test_help_skills_do_not_follow_external_symlinks(self):
        from app.api.endpoints import help_center
        skills = pathlib.Path(self.temp.name) / 'skills'
        (skills / 'fixture').mkdir(parents=True)
        (skills / 'fixture/SKILL.md').write_text('# Safe skill')
        secret = pathlib.Path(self.temp.name) / 'outside'
        secret.write_text('private fixture')
        self.login()
        with patch.object(help_center, 'SKILLS_DIR', skills):
            self.assertEqual(self.client.get('/api/v1/help/skills/fixture').status_code, 200)
            (skills / 'fixture/SKILL.md').unlink()
            (skills / 'fixture/SKILL.md').symlink_to(secret)
            self.assertEqual(self.client.get('/api/v1/help/skills/fixture').status_code, 404)
            self.assertEqual(self.client.get('/api/v1/help/skills').json(), [])

    def test_spa_file_traversal_is_denied(self):
        from app.config import DASHBOARD_DIR
        if not (DASHBOARD_DIR / 'frontend/dist/index.html').exists():
            self.skipTest('Requires built frontend in the local image')
        response = self.client.get('/%2e%2e/%2e%2e/backend/app/config.py')
        self.assertEqual(response.status_code, 400)

    def test_wrong_password_rate_limit_origin_and_host(self):
        self.assertEqual(self.client.post('/api/v1/auth/login', json={'password': 'tester'}).status_code, 401)
        self.assertEqual(self.client.post('/api/v1/auth/login', json={'password': 'fixture-password'}, headers={'Origin': 'https://outside.example'}).status_code, 403)
        self.assertEqual(self.client.get('/api/v1/auth/me', headers={'Host': 'outside.example'}).status_code, 400)
        for _ in range(4):
            self.client.post('/api/v1/auth/login', json={'password': 'bad'})
        limited = self.client.post('/api/v1/auth/login', json={'password': 'fixture-password'})
        self.assertEqual(limited.status_code, 429)
        self.assertEqual(limited.headers['retry-after'], '60')

    def test_websocket_requires_session_and_same_origin_and_revokes_on_logout(self):
        from starlette.websockets import WebSocketDisconnect
        url = '/api/v1/logs/fixture/ws'
        with self.assertRaises(WebSocketDisconnect):
            with self.client.websocket_connect(url, headers={'Origin': 'http://localhost:8080'}):
                pass
        self.login()
        with self.assertRaises(WebSocketDisconnect):
            with self.client.websocket_connect(url, headers={'Origin': 'https://outside.example'}):
                pass
        with self.assertRaises(WebSocketDisconnect):
            with self.client.websocket_connect(url + '?type=unknown', headers={'Origin': 'http://localhost:8080'}):
                pass
        with self.client.websocket_connect(url, headers={'Origin': 'http://localhost:8080'}) as socket:
            self.assertIn('Esperando', socket.receive_text())
            self.assertEqual(self.client.post('/api/v1/auth/logout').status_code, 200)
            with self.assertRaises(WebSocketDisconnect):
                socket.receive_text()

    def test_expiry_unknown_token_and_credential_missing(self):
        from app.core import database
        self.login()
        connection = database.get_db_connection()
        with connection:
            connection.execute('UPDATE dashboard_sessions SET expires_at = 0')
        connection.close()
        self.assertEqual(self.client.get('/api/v1/auth/me').status_code, 401)
        self.assertEqual(self.client.get('/api/v1/auth/me', headers={'Authorization': 'Bearer arbitrary'}).status_code, 401)
        with patch.object(self.auth, 'TESTER_PASSWORD', ''):
            self.assertEqual(self.client.post('/api/v1/auth/login', json={'password': ''}).status_code, 503)


class TestDashboardWorkspaceContainment(unittest.TestCase):
    def setUp(self):
        from app.services.workspace_sync import WorkspaceSyncService
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.workspace = WorkspaceSyncService(self.root / 'workspace')
        self.workspace.create_engagement('a')
        self.workspace.create_engagement('ab')

    def test_sibling_prefix_and_absolute_path_cannot_be_read(self):
        sibling = self.workspace._resolve_dir('ab') / 'secret.txt'
        sibling.write_text('private fixture')
        for path in ('../ab/secret.txt', str(sibling)):
            with self.subTest(path=path), self.assertRaises(FileNotFoundError):
                self.workspace.get_artifact_content('a', path)

    def test_invalid_project_type_and_finding_slug_cannot_write(self):
        from app.models.schemas import FindingCreate
        for name in ('..', '../ab', '/tmp/escape', '.hidden', ''):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.workspace.save_notes(name, 'escape')
        with self.assertRaises(ValueError):
            self.workspace.save_notes('a', 'escape', 'unknown')
        with self.assertRaises(ValueError):
            self.workspace.save_finding('a', FindingCreate(slug='../../escaped', title='fixture'))
        self.assertFalse((self.workspace.ws_path / 'engagements/escaped.md').exists())

    def test_symlink_leaf_directory_and_project_are_rejected(self):
        outside = self.root / 'outside.txt'
        outside.write_text('keep')
        project = self.workspace._resolve_dir('a')
        for relative in ('notes.md', 'loot/credentials.json', 'evidence/link.md'):
            leaf = project / relative
            if leaf.exists():
                leaf.unlink()
            leaf.symlink_to(outside)
            with self.subTest(path=relative), self.assertRaises(ValueError):
                self.workspace.save_notes('a', 'overwritten')
            leaf.unlink()
        self.assertEqual(outside.read_text(), 'keep')

    def test_duplicate_create_preserves_original_notes(self):
        self.workspace.save_notes('a', 'keep')
        with self.assertRaises(ValueError):
            self.workspace.create_engagement('a')
        self.assertEqual(self.workspace.get_notes('a'), 'keep')


class TestVaultKeyPersistence(unittest.TestCase):
    def test_new_key_private_stable_and_invalid_key_preserved(self):
        from app.core.key_store import persistent_key
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / 'key'
            key = persistent_key(path)
            self.assertEqual(len(key), 32)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(persistent_key(path), key)
            path.write_bytes(b'broken')
            with self.assertRaises(RuntimeError):
                persistent_key(path)
            self.assertEqual(path.read_bytes(), b'broken')
            path.unlink()
            external = pathlib.Path(directory) / 'outside'
            external.write_bytes(key)
            path.symlink_to(external)
            with self.assertRaises(OSError):
                persistent_key(path)

    def test_key_write_failure_never_returns_fallback(self):
        from app.core.key_store import persistent_key
        with tempfile.TemporaryDirectory() as directory:
            with patch('app.core.key_store.tempfile.mkstemp', side_effect=PermissionError('fixture')):
                with self.assertRaises(PermissionError):
                    persistent_key(pathlib.Path(directory) / 'key')

    def test_missing_key_with_encrypted_records_does_not_create_new_key(self):
        import sqlite3
        from app.core import security
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            database = root / 'vault.db'
            key = root / 'key'
            connection = sqlite3.connect(database)
            with connection:
                connection.execute('CREATE TABLE api_keys (encrypted_key TEXT)')
                connection.execute("INSERT INTO api_keys VALUES ('fixture ciphertext')")
            connection.close()
            with patch.object(security, 'VAULT_KEY_PATH', key), patch.object(security, 'VAULT_DB_PATH', database):
                with self.assertRaises(RuntimeError):
                    security.get_or_create_vault_key()
            self.assertFalse(key.exists())
