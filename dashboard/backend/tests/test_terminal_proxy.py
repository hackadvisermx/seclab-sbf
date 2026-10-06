import pathlib
import socket
import subprocess
import time
import unittest
from unittest.mock import patch


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class TestTerminalProxy(unittest.TestCase):
    """Fase 114 / backlog A10: el proxy de terminal debe permitir sesión
    única (cookie del dashboard, sin la autenticación HTTP Basic propia de
    ttyd por separado) sin debilitar ninguna de las dos capas de control de
    acceso ya existentes (sesión + origen). Usa un ttyd real (el mismo
    binario de la imagen), no un doble simulado: el protocolo binario de
    ttyd no está documentado de forma estable como para confiar en un mock."""

    @classmethod
    def setUpClass(cls):
        ttyd_bin = pathlib.Path("/usr/bin/ttyd")
        if not ttyd_bin.is_file():
            raise unittest.SkipTest("ttyd no está instalado en este entorno (se requiere la imagen local).")
        cls.ttyd_port = _free_port()
        cls.ttyd_password = "fixture-ttyd-password"
        cls.ttyd_proc = subprocess.Popen(
            [str(ttyd_bin), "-i", "127.0.0.1", "-p", str(cls.ttyd_port), "-c", f"tester:{cls.ttyd_password}", "/bin/sh"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", cls.ttyd_port), timeout=0.2):
                    break
            except OSError:
                time.sleep(0.1)
        else:
            cls.ttyd_proc.kill()
            raise RuntimeError("ttyd de prueba no respondió a tiempo")

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "ttyd_proc", None):
            cls.ttyd_proc.kill()
            cls.ttyd_proc.wait(timeout=5)

    def setUp(self):
        from app.api.endpoints import terminal_proxy
        from app.main import app
        from fastapi.testclient import TestClient

        self.terminal_proxy = terminal_proxy
        self.port_patch = patch.object(terminal_proxy, "TTYD_PORT", self.ttyd_port)
        self.password_patch = patch.object(terminal_proxy, "TTYD_PASSWORD", self.ttyd_password)
        self.port_patch.start()
        self.password_patch.start()
        self.addCleanup(self.port_patch.stop)
        self.addCleanup(self.password_patch.stop)

        from app.api.endpoints import auth
        self.auth = auth
        self.password_dashboard_patch = patch.object(auth, "TESTER_PASSWORD", "dashboard-fixture-password")
        self.password_dashboard_patch.start()
        self.addCleanup(self.password_dashboard_patch.stop)

        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.origin = {"Origin": "http://localhost:8080"}

    def login(self):
        res = self.client.post("/api/v1/auth/login", json={"password": "dashboard-fixture-password"})
        self.assertEqual(res.status_code, 200, res.text)

    def test_http_asset_is_proxied_same_origin_without_exposing_ttyd_password_requirement(self):
        self.login()
        res = self.client.get("/api/v1/terminal/")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"ttyd", res.content.lower())

        token_res = self.client.get("/api/v1/terminal/token")
        self.assertEqual(token_res.status_code, 200)
        self.assertIn("token", token_res.json())

    def test_http_requires_dashboard_session(self):
        res = self.client.get("/api/v1/terminal/")
        self.assertEqual(res.status_code, 401)

    def test_websocket_relays_real_ttyd_banner_end_to_end(self):
        from starlette.websockets import WebSocketDisconnect
        self.login()
        with self.client.websocket_connect("/api/v1/terminal/ws", subprotocols=["tty"], headers=self.origin) as ws:
            banner = ws.receive_bytes()
            self.assertTrue(banner.startswith(b"1"), "ttyd antepone un prefijo de tipo de frame")
            self.assertIn(b"/bin/sh", banner)

    def test_websocket_rejects_without_dashboard_session(self):
        from starlette.websockets import WebSocketDisconnect
        with self.assertRaises(WebSocketDisconnect):
            with self.client.websocket_connect("/api/v1/terminal/ws", subprotocols=["tty"], headers=self.origin):
                pass

    def test_websocket_rejects_wrong_origin_even_with_valid_session(self):
        from starlette.websockets import WebSocketDisconnect
        self.login()
        with self.assertRaises(WebSocketDisconnect):
            with self.client.websocket_connect(
                "/api/v1/terminal/ws", subprotocols=["tty"], headers={"Origin": "https://outside.example"}
            ):
                pass

    def test_missing_ttyd_password_fails_closed(self):
        self.login()
        with patch.object(self.terminal_proxy, "TTYD_PASSWORD", ""):
            res = self.client.get("/api/v1/terminal/")
            self.assertEqual(res.status_code, 503)

            from starlette.websockets import WebSocketDisconnect
            with self.assertRaises(WebSocketDisconnect):
                with self.client.websocket_connect("/api/v1/terminal/ws", subprotocols=["tty"], headers=self.origin):
                    pass


if __name__ == "__main__":
    unittest.main()
