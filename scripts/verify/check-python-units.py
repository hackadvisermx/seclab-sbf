#!/usr/bin/env python3
"""Pruebas unitarias de seguridad para controladores Python de SecLab (proxy y VPN).

Verifica invariantes criticas:
- Bloqueo de rangos IP sensibles (RFC1918, CGNAT, metadata cloud, loopback, Tailscale).
- Normalizacion de direcciones IPv4, IPv6 e IPv4-mapped IPv6.
- Validacion estricta de URLs de destino en pt-web.
- Validacion del request-line HTTP (metodos permitidos, rechazo de absolute-form).
- Codificacion y respuestas binarias de SOCKS5.
- Control de perfiles y acciones autorizadas en vpn-control.
- Formato y limites de respuesta JSON en sockets Unix de control.
"""

import importlib.util
import io
import ipaddress
import json
import os
import pathlib
import sys
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent


def load_module(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"No se pudo cargar el modulo {name} desde {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


proxy_ctrl = load_module("proxy_control", REPO_ROOT / "scripts" / "proxy-control.py")
vpn_ctrl = load_module("vpn_control", REPO_ROOT / "scripts" / "vpn-control.py")
compose_sec = load_module("compose_security", REPO_ROOT / "scripts" / "verify" / "check-compose-security.py")


class MockSocket:
    """Socket simulado en memoria para capturar envios y proveer recepciones."""

    def __init__(self, incoming: bytes = b""):
        self.incoming = io.BytesIO(incoming)
        self.outgoing = io.BytesIO()
        self._timeout = None

    def recv(self, size: int) -> bytes:
        return self.incoming.read(size)

    def sendall(self, data: bytes) -> None:
        self.outgoing.write(data)

    def settimeout(self, timeout: float) -> None:
        self._timeout = timeout

    def close(self) -> None:
        pass


class TestProxyControlIPValidation(unittest.TestCase):
    """Verifica reglas de validacion y filtrado de direcciones IP."""

    def test_normalize_ip_ipv4(self):
        addr = proxy_ctrl.normalize_ip("192.0.2.1")
        self.assertIsInstance(addr, ipaddress.IPv4Address)
        self.assertEqual(str(addr), "192.0.2.1")

    def test_normalize_ip_ipv6(self):
        addr = proxy_ctrl.normalize_ip("2001:db8::1")
        self.assertIsInstance(addr, ipaddress.IPv6Address)
        self.assertEqual(str(addr), "2001:db8::1")

    def test_normalize_ip_ipv4_mapped_ipv6(self):
        addr = proxy_ctrl.normalize_ip("::ffff:192.0.2.1")
        self.assertIsInstance(addr, ipaddress.IPv4Address)
        self.assertEqual(str(addr), "192.0.2.1")

    def test_blocked_ip_loopback(self):
        self.assertTrue(proxy_ctrl.blocked_ip("127.0.0.1"))
        self.assertTrue(proxy_ctrl.blocked_ip("127.0.1.1"))
        self.assertTrue(proxy_ctrl.blocked_ip("::1"))

    def test_blocked_ip_unspecified(self):
        self.assertTrue(proxy_ctrl.blocked_ip("0.0.0.0"))
        self.assertTrue(proxy_ctrl.blocked_ip("::"))

    def test_blocked_ip_link_local(self):
        self.assertTrue(proxy_ctrl.blocked_ip("169.254.1.1"))
        self.assertTrue(proxy_ctrl.blocked_ip("fe80::1"))

    def test_blocked_ip_multicast(self):
        self.assertTrue(proxy_ctrl.blocked_ip("224.0.0.1"))
        self.assertTrue(proxy_ctrl.blocked_ip("ff02::1"))

    def test_blocked_ip_cloud_metadata(self):
        # Metadata endpoint comun a AWS, GCP, Azure, OCI, DO
        self.assertTrue(proxy_ctrl.blocked_ip("169.254.169.254"))

    def test_blocked_ip_azure_wire_server(self):
        self.assertTrue(proxy_ctrl.blocked_ip("168.63.129.16"))

    def test_blocked_ip_cgnat(self):
        # 100.64.0.0/10 (usado por Tailscale y proveedores CGNAT)
        self.assertTrue(proxy_ctrl.blocked_ip("100.64.0.1"))
        self.assertTrue(proxy_ctrl.blocked_ip("100.100.100.100"))
        self.assertTrue(proxy_ctrl.blocked_ip("100.127.255.254"))

    def test_blocked_ip_docker_bridges(self):
        # Subredes Docker 172.17.0.0/16 a 172.31.0.0/16
        self.assertTrue(proxy_ctrl.blocked_ip("172.17.0.1"))
        self.assertTrue(proxy_ctrl.blocked_ip("172.20.0.1"))
        self.assertTrue(proxy_ctrl.blocked_ip("172.31.255.254"))

    def test_blocked_ip_tailscale_ipv6(self):
        # Rango ULA IPv6 de Tailscale fd7a:115c:a1e0::/48
        self.assertTrue(proxy_ctrl.blocked_ip("fd7a:115c:a1e0::1"))
        self.assertTrue(proxy_ctrl.blocked_ip("fd7a:115c:a1e0:0001::5"))

    def test_blocked_ip_benchmark_dummy(self):
        self.assertTrue(proxy_ctrl.blocked_ip("192.0.0.192"))
        self.assertTrue(proxy_ctrl.blocked_ip("198.18.0.1"))

    def test_allowed_target_ips(self):
        # Destinos legitimos tipicos de laboratorios y VPN
        self.assertFalse(proxy_ctrl.blocked_ip("10.10.10.10"))  # HTB
        self.assertFalse(proxy_ctrl.blocked_ip("10.11.1.1"))  # THM
        self.assertFalse(proxy_ctrl.blocked_ip("93.184.216.34"))  # example.com
        self.assertFalse(proxy_ctrl.blocked_ip("1.1.1.1"))  # Cloudflare


class TestProxyControlWebTarget(unittest.TestCase):
    """Verifica el analisis de destinos web en pt-web."""

    def test_parse_valid_http(self):
        host, port, tls = proxy_ctrl.parse_web_target("http://10.10.10.10")
        self.assertEqual(host, "10.10.10.10")
        self.assertEqual(port, 80)
        self.assertFalse(tls)

    def test_parse_valid_https(self):
        host, port, tls = proxy_ctrl.parse_web_target("https://10.10.10.10")
        self.assertEqual(host, "10.10.10.10")
        self.assertEqual(port, 443)
        self.assertTrue(tls)

    def test_parse_valid_custom_port(self):
        host, port, tls = proxy_ctrl.parse_web_target("http://target.htb:8080/")
        self.assertEqual(host, "target.htb")
        self.assertEqual(port, 8080)
        self.assertFalse(tls)

    def test_reject_unsupported_scheme(self):
        with self.assertRaises(proxy_ctrl.ProxyError):
            proxy_ctrl.parse_web_target("ftp://target.htb")
        with self.assertRaises(proxy_ctrl.ProxyError):
            proxy_ctrl.parse_web_target("ws://target.htb")

    def test_reject_path_in_target(self):
        with self.assertRaises(proxy_ctrl.ProxyError):
            proxy_ctrl.parse_web_target("http://target.htb/admin")

    def test_reject_query_in_target(self):
        with self.assertRaises(proxy_ctrl.ProxyError):
            proxy_ctrl.parse_web_target("http://target.htb?id=1")

    def test_reject_credentials_in_target(self):
        with self.assertRaises(proxy_ctrl.ProxyError):
            proxy_ctrl.parse_web_target("http://admin:secret@target.htb")


class TestProxyControlHttpRequest(unittest.TestCase):
    """Verifica la validacion de peticiones HTTP en pt-web."""

    def test_valid_get_request(self):
        sock = MockSocket(b"GET /index.html HTTP/1.1\r\nHost: target\r\n\r\n")
        data = proxy_ctrl.read_http_request(sock)
        self.assertTrue(data.startswith(b"GET /index.html HTTP/1.1\r\n"))

    def test_valid_post_request(self):
        sock = MockSocket(b"POST /api/login HTTP/1.1\r\nHost: target\r\nContent-Length: 0\r\n\r\n")
        data = proxy_ctrl.read_http_request(sock)
        self.assertTrue(data.startswith(b"POST /api/login HTTP/1.1\r\n"))

    def test_valid_options_star_request(self):
        sock = MockSocket(b"OPTIONS * HTTP/1.1\r\nHost: target\r\n\r\n")
        data = proxy_ctrl.read_http_request(sock)
        self.assertTrue(data.startswith(b"OPTIONS * HTTP/1.1\r\n"))

    def test_reject_invalid_method(self):
        sock = MockSocket(b"FOOBAR / HTTP/1.1\r\nHost: target\r\n\r\n")
        with self.assertRaises(proxy_ctrl.ProxyError):
            proxy_ctrl.read_http_request(sock)

    def test_reject_http2_request(self):
        sock = MockSocket(b"GET / HTTP/2.0\r\nHost: target\r\n\r\n")
        with self.assertRaises(proxy_ctrl.ProxyError):
            proxy_ctrl.read_http_request(sock)

    def test_reject_absolute_form_target(self):
        # Evita que el cliente use pt-web como proxy abierto usando URLs absolutas
        sock = MockSocket(b"GET http://evil.com/ HTTP/1.1\r\nHost: evil.com\r\n\r\n")
        with self.assertRaises(proxy_ctrl.ProxyError):
            proxy_ctrl.read_http_request(sock)


class TestProxyControlSocks5(unittest.TestCase):
    """Verifica codificacion binaria de respuestas SOCKS5."""

    def test_socks_reply_ipv4(self):
        sock = MockSocket()
        proxy_ctrl.socks_reply(sock, 0, "10.10.10.10", 80)
        output = sock.outgoing.getvalue()
        # [0x05, 0x00, 0x00, 0x01 (IPv4), 4 bytes IP, 2 bytes port]
        self.assertEqual(len(output), 10)
        self.assertEqual(output[:4], b"\x05\x00\x00\x01")
        self.assertEqual(output[4:8], bytes([10, 10, 10, 10]))
        self.assertEqual(int.from_bytes(output[8:10], "big"), 80)

    def test_socks_reply_error_code(self):
        sock = MockSocket()
        proxy_ctrl.socks_reply(sock, 1)  # General SOCKS server failure
        output = sock.outgoing.getvalue()
        self.assertEqual(output[0:3], b"\x05\x01\x00")


class TestVpnControl(unittest.TestCase):
    """Verifica listas de control de acceso y protocolos en vpn-control."""

    def test_allowed_actions_whitelist(self):
        expected_actions = {"list", "status", "doctor", "connect", "disconnect", "switch"}
        self.assertEqual(vpn_ctrl.ALLOWED_ACTIONS, expected_actions)

    def test_allowed_profiles_whitelist(self):
        expected_profiles = {"tryhackme", "try", "hackthebox", "htb", "client", "cli"}
        self.assertEqual(vpn_ctrl.ALLOWED_PROFILES, expected_profiles)

    def test_manager_command_construction(self):
        cmd_status = vpn_ctrl.manager_command("status")
        self.assertEqual(cmd_status, ["/usr/local/bin/vpn-manager", "status"])

        cmd_connect = vpn_ctrl.manager_command("connect", "tryhackme")
        self.assertEqual(cmd_connect, ["/usr/local/bin/vpn-manager", "connect", "tryhackme"])

    def test_response_payload_framing(self):
        payload = vpn_ctrl.response_payload(0, "salida ok", "")
        self.assertTrue(payload.endswith("\n"))
        parsed = json.loads(payload.strip())
        self.assertEqual(parsed["code"], 0)
        self.assertEqual(parsed["stdout"], "salida ok")
        self.assertEqual(parsed["stderr"], "")

    def test_output_limit_truncation(self):
        short_text = "test output"
        self.assertEqual(vpn_ctrl.output_limit(short_text), short_text)

        long_text = "A" * 20000
        truncated = vpn_ctrl.output_limit(long_text)
        self.assertEqual(len(truncated), 16000)


class TestComposeSecurityAuditor(unittest.TestCase):
    """Verifica reglas de auditoria de seguridad para Docker Compose."""

    def test_valid_hardened_service(self):
        config = {
            "services": {
                "lab": {
                    "cap_drop": ["ALL"],
                    "cap_add": ["NET_ADMIN"],
                    "security_opt": ["no-new-privileges:true"],
                    "volumes": ["/home/user/workspace:/workspace"],
                }
            }
        }
        issues = compose_sec.analyze_compose(config, name="test")
        self.assertEqual(issues, [])

    def test_detect_privileged_container(self):
        config = {
            "services": {
                "lab": {
                    "privileged": True,
                    "cap_drop": ["ALL"],
                    "security_opt": ["no-new-privileges:true"],
                }
            }
        }
        issues = compose_sec.analyze_compose(config, name="test")
        self.assertTrue(any("privileged: true" in i for i in issues))

    def test_detect_network_mode_host(self):
        config = {
            "services": {
                "lab": {
                    "network_mode": "host",
                    "cap_drop": ["ALL"],
                    "security_opt": ["no-new-privileges:true"],
                }
            }
        }
        issues = compose_sec.analyze_compose(config, name="test")
        self.assertTrue(any("network_mode: host" in i for i in issues))

    def test_detect_dangerous_capabilities(self):
        config = {
            "services": {
                "lab": {
                    "cap_drop": ["ALL"],
                    "cap_add": ["SYS_ADMIN", "SYS_PTRACE"],
                    "security_opt": ["no-new-privileges:true"],
                }
            }
        }
        issues = compose_sec.analyze_compose(config, name="test")
        self.assertTrue(any("capacidades peligrosas" in i for i in issues))

    def test_detect_docker_sock_mount(self):
        config = {
            "services": {
                "lab": {
                    "cap_drop": ["ALL"],
                    "security_opt": ["no-new-privileges:true"],
                    "volumes": [
                        {"source": "/var/run/docker.sock", "target": "/var/run/docker.sock"}
                    ],
                }
            }
        }
        issues = compose_sec.analyze_compose(config, name="test")
        self.assertTrue(any("socket de Docker" in i for i in issues))

    def test_detect_public_port_binding(self):
        config = {
            "services": {
                "lab": {
                    "cap_drop": ["ALL"],
                    "security_opt": ["no-new-privileges:true"],
                    "ports": [{"host_ip": "0.0.0.0", "published": 2222, "target": 2222}],
                }
            }
        }
        issues = compose_sec.analyze_compose(config, name="test")
        self.assertTrue(any("0.0.0.0" in i for i in issues))

    def test_allow_loopback_port_binding(self):
        config = {
            "services": {
                "lab": {
                    "cap_drop": ["ALL"],
                    "security_opt": ["no-new-privileges:true"],
                    "ports": [{"host_ip": "127.0.0.1", "published": 2222, "target": 2222}],
                }
            }
        }
        issues = compose_sec.analyze_compose(config, name="test")
        self.assertEqual(issues, [])

    def test_detect_missing_cap_drop_all(self):
        config = {
            "services": {
                "lab": {
                    "cap_drop": ["NET_RAW"],
                    "security_opt": ["no-new-privileges:true"],
                }
            }
        }
        issues = compose_sec.analyze_compose(config, name="test")
        self.assertTrue(any("cap_drop: ALL" in i for i in issues))

    def test_detect_missing_no_new_privileges(self):
        config = {
            "services": {
                "lab": {
                    "cap_drop": ["ALL"],
                }
            }
        }
        issues = compose_sec.analyze_compose(config, name="test")
        self.assertTrue(any("no-new-privileges" in i for i in issues))


class TestPivotingToolkitAndConfig(unittest.TestCase):
    """Verifica la configuracion y manifiestos de las herramientas de pivoting."""

    def test_tools_json_manifest_consistency(self):
        tools_file = REPO_ROOT / "shell" / "tools.json"
        self.assertTrue(tools_file.is_file())
        with open(tools_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        installed = set(data.get("installed", []))
        tools = set(data.get("tools", {}).keys())
        self.assertEqual(installed, tools, f"Desincronizacion en tools.json: {installed ^ tools}")

        for tool_name in ["chisel", "ligolo-proxy", "proxychains4"]:
            self.assertIn(tool_name, tools, f"{tool_name} debe estar en tools.json")
            tool_entry = data["tools"][tool_name]
            self.assertEqual(tool_entry["category"], "network")
            self.assertTrue(len(tool_entry["description"]) > 10)

    def test_proxychains_config_security_and_format(self):
        conf_file = REPO_ROOT / "security" / "proxychains" / "proxychains4.conf"
        self.assertTrue(conf_file.is_file())
        content = conf_file.read_text(encoding="utf-8")

        self.assertIn("dynamic_chain", content)
        self.assertIn("proxy_dns", content)
        self.assertIn("quiet_mode", content)
        self.assertIn("[ProxyList]", content)

        # Invariante: solo proxies en loopback 127.0.0.1 por defecto
        proxy_lines = [
            line.strip()
            for line in content.splitlines()
            if line.strip() and not line.strip().startswith("#") and "[ProxyList]" not in line
        ]
        self.assertTrue(len(proxy_lines) >= 1)
        for line in proxy_lines:
            parts = line.split()
            if parts[0] in ("socks4", "socks5", "http"):
                ip = parts[1]
                self.assertEqual(ip, "127.0.0.1", f"Proxy por defecto no es loopback: {line}")
                self.assertEqual(parts[2], "1080", f"Puerto por defecto no es 1080: {line}")

    def test_tools_lock_tracks_pivoting_artifacts(self):
        lock_file = REPO_ROOT / "supply-chain" / "tools.lock.yaml"
        self.assertTrue(lock_file.is_file())
        content = lock_file.read_text(encoding="utf-8")
        self.assertIn("chisel", content)
        self.assertIn("ligolo-ng", content)
        self.assertIn("proxychains4", content)
        self.assertIn("libproxychains4", content)

    def test_tools_lock_tracks_web_recon_artifacts(self):
        lock_file = REPO_ROOT / "supply-chain" / "tools.lock.yaml"
        self.assertTrue(lock_file.is_file())
        content = lock_file.read_text(encoding="utf-8")

        self.assertIn("gf", content)
        self.assertIn("qsreplace", content)
        self.assertIn("gf-patterns", content)

    def test_tools_lock_tracks_gef(self):
        lock_file = REPO_ROOT / "supply-chain" / "tools.lock.yaml"
        self.assertTrue(lock_file.is_file())
        content = lock_file.read_text(encoding="utf-8")

        self.assertIn("gef", content)
        self.assertIn("GDB Enhanced Features", content)

    def test_tools_lock_tracks_assetfinder_and_httprobe(self):
        lock_file = REPO_ROOT / "supply-chain" / "tools.lock.yaml"
        self.assertTrue(lock_file.is_file())
        content = lock_file.read_text(encoding="utf-8")

        self.assertIn("assetfinder", content)
        self.assertIn("httprobe", content)
        self.assertIn("Descubrimiento de dominios y subdominios relacionados", content)

    def test_tools_lock_tracks_findomain(self):
        lock_file = REPO_ROOT / "supply-chain" / "tools.lock.yaml"
        self.assertTrue(lock_file.is_file())
        content = lock_file.read_text(encoding="utf-8")

        self.assertIn("findomain", content)
        self.assertIn("findomain-linux.zip", content)
        self.assertIn("findomain-aarch64.zip", content)

    def test_pentest_lab_plugin_helpers_and_aliases(self):
        plugin_file = REPO_ROOT / "shell" / "pentest-lab" / "pentest-lab.plugin.zsh"
        self.assertTrue(plugin_file.is_file())
        content = plugin_file.read_text(encoding="utf-8")

        # Invariantes: helpers de ergonomia y reconocimiento
        expected_helpers = [
            "pt-extractports()",
            "pt-nmp()",
            "pt-serv-web()",
            "pt-serv-smb()",
            "pt-s3-ls()",
            "pt-recon()",
        ]
        for helper in expected_helpers:
            self.assertIn(helper, content, f"Helper no encontrado en plugin: {helper}")

        # Aliases ergonomicos compatibles
        expected_aliases = [
            'alias nmp="pt-nmp"',
            'alias extractports="pt-extractports"',
            'alias webserverhere="pt-serv-web"',
            'alias smbserverhere="pt-serv-smb"',
            'alias awsl="pt-s3-ls"',
        ]
        for alias in expected_aliases:
            self.assertIn(alias, content, f"Alias no encontrado en plugin: {alias}")

        # pt-help incluye mención a helpers
        self.assertIn("pt-nmp", content)
        self.assertIn("pt-recon", content)
        self.assertIn("pt-serv-web", content)


def main():
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if result.wasSuccessful():
        print("python_units_check=ok")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
