import ipaddress
import pathlib
import tempfile
import unittest
from unittest.mock import patch

from app.services.telemetry import telemetry_service, TelemetryService


class TestNetworkTelemetry(unittest.TestCase):
    def setUp(self):
        self.service = TelemetryService()

    def test_get_local_ip_returns_valid_ipv4(self):
        ip = self.service.get_local_ip()
        self.assertIsInstance(ip, str)
        self.assertTrue(len(ip) > 0)
        # Debe ser una dirección IPv4 válida
        parsed = ipaddress.IPv4Address(ip)
        self.assertIsNotNone(parsed)

    def test_system_telemetry_contains_local_ip_and_vpn(self):
        telem = self.service.get_system_telemetry()
        self.assertIn("local_ip", telem)
        self.assertIsInstance(telem["local_ip"], str)
        self.assertIn("vpn", telem)
        self.assertIn("ip", telem["vpn"])
        self.assertIn("connected", telem["vpn"])
        self.assertIn("hostname", telem)
        self.assertIn("tailscale", telem)

    def test_get_local_ip_fallback_when_subprocess_fails(self):
        with patch("subprocess.run", side_effect=FileNotFoundError("ip binary not found")):
            ip = self.service.get_local_ip()
            self.assertIsInstance(ip, str)
            parsed = ipaddress.IPv4Address(ip)
            self.assertIsNotNone(parsed)

    def test_api_telemetry_endpoint_returns_local_ip(self):
        from app.main import app
        from app.api.endpoints import auth
        from app.core import database
        from fastapi.testclient import TestClient

        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        with patch.object(database, "VAULT_DB_PATH", pathlib.Path(temp.name) / "test.db"):
            database.init_db()
            auth._attempts.clear()
            with patch.object(auth, "TESTER_PASSWORD", "fixture-password"):
                client = TestClient(app)
                # Login para obtener cookie de sesión
                login_res = client.post("/api/v1/auth/login", json={"password": "fixture-password"})
                self.assertEqual(login_res.status_code, 200)

                # Petición a /api/v1/system/telemetry
                res = client.get("/api/v1/system/telemetry")
                self.assertEqual(res.status_code, 200)
                data = res.json()
                self.assertIn("local_ip", data)
                self.assertIn("vpn", data)
                self.assertIn("hostname", data)
                self.assertIsInstance(data["local_ip"], str)
                client.close()
