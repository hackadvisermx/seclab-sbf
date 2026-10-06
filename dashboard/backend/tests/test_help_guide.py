import os
import pathlib
import tempfile
import unittest
from unittest.mock import patch


class TestHelpGuideEndpoint(unittest.TestCase):
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

    def test_unauthenticated_request_to_guide_returns_401(self):
        response = self.client.get('/api/v1/help/guide')
        self.assertEqual(response.status_code, 401)

    def test_authenticated_request_to_guide_returns_200_html(self):
        self.login()
        response = self.client.get('/api/v1/help/guide')
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers.get("content-type", ""))
        html = response.text
        self.assertIn("SecLab-SBF", html)
        self.assertIn("Guía del Operador", html)
        self.assertIn("Auditoría Web / API", html)
        self.assertIn("Reto CTF / Máquina", html)
        self.assertIn("Scope Guard", html)
        self.assertIn("pt-recon", html)
        self.assertIn("HERRAMIENTAS", html)

    def test_missing_or_symlink_guide_file_returns_404(self):
        self.login()
        fake_path = pathlib.Path(self.temp.name) / "non_existent_guide.html"
        from app.api.endpoints import help_center
        with patch.object(help_center, 'GUIDE_HTML_FILE', fake_path):
            response = self.client.get('/api/v1/help/guide')
            self.assertEqual(response.status_code, 404)
            self.assertIn("no encontrada", response.text)
