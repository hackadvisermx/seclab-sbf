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
from unittest.mock import patch

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
scope_validator = load_module("scope_validator", REPO_ROOT / "scripts" / "pt-scope-validator.py")
report_compiler = load_module("report_compiler", REPO_ROOT / "scripts" / "pt-report-compiler.py")
agent_context = load_module("agent_context", REPO_ROOT / "scripts" / "pt-agent-context.py")
engagement_packer = load_module("engagement_packer", REPO_ROOT / "scripts" / "pt-engagement-packer.py")
recon_pipeline = load_module("recon_pipeline", REPO_ROOT / "scripts" / "pt-recon-pipeline.py")
audit_checklist = load_module("audit_checklist", REPO_ROOT / "scripts" / "pt-audit-checklist.py")
audit_next = load_module("audit_next", REPO_ROOT / "scripts" / "pt-audit-next.py")
guide_helper = load_module("guide_helper", REPO_ROOT / "scripts" / "pt-guide.py")


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

    def test_tools_lock_tracks_post_exploit_payloads(self):
        lock_file = REPO_ROOT / "supply-chain" / "tools.lock.yaml"
        self.assertTrue(lock_file.is_file())
        content = lock_file.read_text(encoding="utf-8")

        self.assertIn("post_exploit_payloads:", content)
        self.assertIn("linpeas.sh", content)
        self.assertIn("winPEAS.bat", content)
        self.assertIn("winPEASany.exe", content)
        self.assertIn("socat_linux_amd64", content)
        self.assertIn("socat_linux_arm64", content)
        self.assertIn("nc.exe", content)
        self.assertIn("nc64.exe", content)
        # Checksums verificados
        self.assertIn("795e315c42c58e27841e4ee2798a73a9309694f0454b34707299bb090e04b98d", content)
        self.assertIn("11e4ea92ce2465f3d30c5a56fd4aeba2aecaf4d1c2670ac42bd61c4db2becf87", content)
        self.assertIn("af0154c95d2897e78450d93a05479efca8b315b51e82ad70cd1dc4f94a5ecff5", content)
        self.assertIn("19fd284b8d48feff2a15cc37bd9ba070223da575e4e84623aea4b88f6efeb597", content)
        self.assertIn("758f023d9a27ae3b7f5f633ef41bed65b812af0dd86b4afede37925e405ddc3d", content)
        self.assertIn("e8fbec25db4f9d95b5e8f41cca51a4b32be8674a4dea7a45b6f7aeb22dbc38db", content)
        self.assertIn("3e59379f585ebf0becb6b4e06d0fbbf806de28a4bb256e837b4555f1b4245571", content)

    def test_tools_lock_tracks_x8_and_gau(self):
        lock_file = REPO_ROOT / "supply-chain" / "tools.lock.yaml"
        self.assertTrue(lock_file.is_file())
        content = lock_file.read_text(encoding="utf-8")

        self.assertIn("gau", content)
        self.assertIn("5d4e1270e632732756fe98717520c43c86e8bd18", content)
        self.assertIn("github.com/sirupsen/logrus: v1.9.3", content)
        self.assertIn("github.com/valyala/fasthttp: v1.74.0", content)

        self.assertIn("x8", content)
        self.assertIn("x86_64-linux-x8.gz", content)
        self.assertIn("x8-1:v4.3.0.r10.gc78f246-1-aarch64.pkg.tar.zst", content)
        self.assertIn("b3e54da4c0cc62163a3485addea6671368ee69342ea5740e56d6d6112196bd0e", content)
        self.assertIn("35f355231ac2420eca6aa466e8fdf9f71542bb81726b46930ea9885c29ef1b4c", content)

    def test_pentest_lab_plugin_helpers_and_aliases(self):
        plugin_file = REPO_ROOT / "shell" / "pentest-lab" / "pentest-lab.plugin.zsh"
        self.assertTrue(plugin_file.is_file())
        content = plugin_file.read_text(encoding="utf-8")

        # Invariantes: helpers de ergonomia y reconocimiento
        expected_helpers = [
            "pt-cheat()",
            "pt-log()",
            "pt-scope()",
            "pt-eng()",
            "pt-finding()",
            "pt-report()",
            "pt-context()",
            "pt-extractports()",
            "pt-nmp()",
            "pt-serv-web()",
            "pt-callback()",
            "pt-serv-smb()",
            "pt-serv-payloads()",
            "pt-s3-ls()",
            "pt-fuzz-params()",
            "pt-recon()",
            "pt-guide()",
        ]
        for helper in expected_helpers:
            self.assertIn(helper, content, f"Helper no encontrado en plugin: {helper}")

        # Aliases ergonomicos compatibles
        expected_aliases = [
            'alias nmp="pt-nmp"',
            'alias extractports="pt-extractports"',
            'alias webserverhere="pt-serv-web"',
            'alias smbserverhere="pt-serv-smb"',
            'alias servpayloads="pt-serv-payloads"',
            'alias payloadserver="pt-serv-payloads"',
            'alias fuzzparams="pt-fuzz-params"',
            'alias awsl="pt-s3-ls"',
            'alias ptcheat="pt-cheat"',
            'alias cheat="pt-cheat"',
            'alias ptlog="pt-log"',
            'alias logeng="pt-log"',
            'alias ptskills="pt-skills"',
            'alias skills="pt-skills"',
            'alias pt-skill="pt-skills"',
            'alias pteng="pt-eng"',
            'alias engagement="pt-eng"',
            'alias ptscope="pt-scope"',
            'alias scopecheck="pt-scope"',
            'alias ptfinding="pt-finding"',
            'alias ptvuln="pt-finding"',
            'alias finding="pt-finding"',
            'alias vuln="pt-finding"',
            'alias ptreport="pt-report"',
            'alias report="pt-report"',
            'alias ptcallback="pt-callback"',
            'alias callback="pt-callback"',
            'alias ptcontext="pt-context"',
            'alias agentcontext="pt-context"',
            'alias pt-ctx="pt-context"',
            'alias ctx="pt-context"',
            'alias ptpack="pt-eng pack"',
            'alias engpack="pt-eng pack"',
            'alias ptclose="pt-eng close"',
            'alias ptrecon="pt-recon"',
            'alias reconpipeline="pt-recon"',
            'alias recon="pt-recon"',
            'alias ptcheck="pt-checklist"',
            'alias engcheck="pt-eng check"',
            'alias coverage="pt-checklist"',
            'alias ptnext="pt-next"',
            'alias engnext="pt-eng next"',
            'alias next="pt-next"',
            'alias ptguide="pt-guide"',
            'alias guia="pt-guide"',
            'alias guide="pt-guide"',
            'alias engguide="pt-eng guide"',
        ]
        for alias in expected_aliases:
            self.assertIn(alias, content, f"Alias no encontrado en plugin: {alias}")

        self.assertIn("_pt-packer-script()", content)
        self.assertIn("_pt-recon-script()", content)
        self.assertIn("_pt-checklist-script()", content)
        self.assertIn("_pt-next-script()", content)
        self.assertIn("_pt-guide-script()", content)

        # pt-help incluye mención a helpers
        self.assertIn("pt-guide", content)
        self.assertIn("pt-next", content)
        self.assertIn("pt-checklist", content)
        self.assertIn("pt-context", content)
        self.assertIn("pt-callback", content)
        self.assertIn("pt-finding", content)
        self.assertIn("pt-report", content)
        self.assertIn("pt-eng", content)
        self.assertIn("pt-scope", content)
        self.assertIn("pt-skills", content)
        self.assertIn("pt-cheat", content)
        self.assertIn("pt-log", content)
        self.assertIn("pt-nmp", content)
        self.assertIn("pt-recon", content)
        self.assertIn("pt-serv-web", content)
        self.assertIn("pt-serv-payloads", content)
        self.assertIn("pt-fuzz-params", content)

    def test_engagement_logging_helpers(self):
        """Verifica la implementacion modular y defensiva de pt-log para auditoria."""
        plugin_file = REPO_ROOT / "shell" / "pentest-lab" / "pentest-lab.plugin.zsh"
        self.assertTrue(plugin_file.is_file())
        content = plugin_file.read_text(encoding="utf-8")

        # Subcomandos modulares
        subcommands = [
            "_pt-log-workspace-dir()",
            "_pt-log-start()",
            "_pt-log-stop()",
            "_pt-log-status()",
            "_pt-log-mark()",
            "_pt-log-list()",
            "_pt-log-view()",
            "_pt-log-tail()",
            "_pt-log-help()",
        ]
        for subcmd in subcommands:
            self.assertIn(subcmd, content, f"Subcomando no encontrado en pt-log: {subcmd}")

        # Invariantes de seguridad: validacion alfanumerica y tmux pipe-pane
        self.assertIn("tmux pipe-pane -o", content)
        self.assertIn("^[a-zA-Z0-9._-]+$", content)
        self.assertIn("terminal.log", content)
        self.assertIn("SECLAB AUDIT LOG STARTED", content)
        self.assertIn("SECLAB AUDIT LOG STOPPED", content)
        self.assertIn("@seclab_log_file", content)

    def test_cheatsheet_dataset_integrity(self):
        """Verifica existencia, formato TSV y validez del catalogo cheatsheet.tsv."""
        tsv_file = REPO_ROOT / "shell" / "pentest-lab" / "cheatsheet.tsv"
        self.assertTrue(tsv_file.is_file(), "cheatsheet.tsv no existe")
        content = tsv_file.read_text(encoding="utf-8")
        lines = [line.strip() for line in content.splitlines() if line.strip() and not line.startswith("#")]

        self.assertGreaterEqual(len(lines), 40, f"Se esperaban al menos 40 comandos en cheatsheet, encontrados {len(lines)}")

        allowed_categories = {"ad", "pivot", "tty", "web", "staging", "crack", "net"}
        found_categories = set()

        for idx, line in enumerate(lines, 1):
            parts = line.split("\t")
            self.assertEqual(len(parts), 4, f"Linea {idx} no contiene exactamente 4 columnas: {line}")
            cat, title, cmd, desc = parts
            self.assertIn(cat, allowed_categories, f"Categoria invalida '{cat}' en linea {idx}")
            self.assertGreater(len(title.strip()), 3, f"Titulo demasiado corto en linea {idx}")
            self.assertGreater(len(cmd.strip()), 5, f"Comando demasiado corto en linea {idx}")
            self.assertGreater(len(desc.strip()), 10, f"Descripcion demasiado corta en linea {idx}")
            found_categories.add(cat)

        self.assertEqual(found_categories, allowed_categories, f"Faltan categorias en cheatsheet: {allowed_categories ^ found_categories}")

    def test_agent_security_skills_framework(self):
        """Verifica la integridad estructural y formato de las Agent Security Skills."""
        skills_dir = REPO_ROOT / "skills"
        seed_skills_dir = REPO_ROOT / "workspace-seed" / "skills"

        self.assertTrue(skills_dir.is_dir(), "Directorio skills/ no existe")
        self.assertTrue(seed_skills_dir.is_dir(), "Directorio workspace-seed/skills/ no existe")

        skills_readme = skills_dir / "README.md"
        self.assertTrue(skills_readme.is_file(), "skills/README.md no existe")

        expected_skills = {
            "recon-profiling": "recon",
            "param-discovery": "fuzzing",
            "triage-gatekeeper": "triage",
            "report-generation": "reporting",
            "auth-matrix-audit": "auth",
            "business-logic-audit": "logic",
            "client-side-spa-audit": "client",
            "api-security-audit": "api",
            "ssrf-injection-audit": "injection",
            "duplicate-scope-guard": "guard",
        }

        for skill_name, category in expected_skills.items():
            skill_path = skills_dir / skill_name
            self.assertTrue(skill_path.is_dir(), f"Directorio de skill no existe: {skill_name}")

            skill_md = skill_path / "SKILL.md"
            self.assertTrue(skill_md.is_file(), f"SKILL.md no existe en {skill_name}")

            content = skill_md.read_text(encoding="utf-8")
            self.assertTrue(content.startswith("---\n"), f"SKILL.md debe iniciar con frontmatter YAML: {skill_name}")

            # Extraer y validar frontmatter
            parts = content.split("---\n", 2)
            self.assertGreaterEqual(len(parts), 3, f"Frontmatter malformado en {skill_name}")
            fm_text = parts[1]

            fm_dict = {}
            for line in fm_text.splitlines():
                if ":" in line and not line.startswith(" ") and not line.startswith("-"):
                    k, v = line.split(":", 1)
                    fm_dict[k.strip()] = v.strip()

            self.assertEqual(fm_dict.get("name"), skill_name, f"El campo 'name' no coincide con el directorio: {skill_name}")
            self.assertEqual(fm_dict.get("category"), category, f"Categoria incorrecta para {skill_name}")
            self.assertTrue(len(fm_dict.get("description", "")) > 15, f"Descripcion demasiado corta en {skill_name}")
            self.assertEqual(fm_dict.get("author"), "hackadvisermx/seclab-sbf")

            # Validar secciones metodologicas criticas
            body = parts[2]
            self.assertIn("## 1. Propósito y Alcance", body, f"Falta seccion de proposito en {skill_name}")
            self.assertIn("## 2. Precondiciones y Guardrails", body, f"Falta seccion de guardrails en {skill_name}")
            self.assertIn("## 3. Flujo de Ejecución", body, f"Falta seccion de flujo en {skill_name}")

            # Validar reflejo en workspace-seed/skills/
            seed_skill_md = seed_skills_dir / skill_name / "SKILL.md"
            self.assertTrue(seed_skill_md.is_file(), f"Skill no reflejada en workspace-seed: {skill_name}")
            self.assertEqual(content, seed_skill_md.read_text(encoding="utf-8"), f"Discrepancia de contenido en workspace-seed para {skill_name}")

        # Validar existencia del helper interactivo pt-skills y selector de prompts en el plugin Zsh
        plugin_file = REPO_ROOT / "shell" / "pentest-lab" / "pentest-lab.plugin.zsh"
        self.assertTrue(plugin_file.is_file())
        plugin_content = plugin_file.read_text(encoding="utf-8")
        self.assertIn("pt-skills-dir()", plugin_content)
        self.assertIn("pt-prompts-dir()", plugin_content)
        self.assertIn("pt-skills()", plugin_content)
        self.assertIn("SECLAB-Skills >", plugin_content)
        self.assertIn("SECLAB-Prompts >", plugin_content)

        # Validar existencia de la suite completa de plantillas de prompts para agentes (6 roles)
        prompt_templates = [
            "recon-agent.prompt.md",
            "auth-agent.prompt.md",
            "logic-agent.prompt.md",
            "injection-agent.prompt.md",
            "triage-agent.prompt.md",
            "report-agent.prompt.md",
        ]
        seed_prompts_dir = REPO_ROOT / "workspace-seed" / "templates" / "prompts"
        skills_prompts_dir = REPO_ROOT / "skills" / "prompts"
        self.assertTrue(seed_prompts_dir.is_dir(), "Directorio workspace-seed/templates/prompts no existe")
        self.assertTrue(skills_prompts_dir.is_dir(), "Directorio skills/prompts no existe")
        for pt in prompt_templates:
            seed_pt = seed_prompts_dir / pt
            skills_pt = skills_prompts_dir / pt
            self.assertTrue(seed_pt.is_file(), f"Prompt template no existe en workspace-seed: {pt}")
            self.assertTrue(skills_pt.is_file(), f"Prompt template no existe en skills/prompts: {pt}")
            self.assertEqual(seed_pt.read_text(encoding="utf-8"), skills_pt.read_text(encoding="utf-8"))

    def test_engagement_scaffolding_and_scope_guard(self):
        """Verifica la especificacion target.yaml, motor de scope y scaffolding pt-eng."""
        # 1. Validar plantilla target.yaml
        target_template = REPO_ROOT / "workspace-seed" / "templates" / "target.yaml"
        self.assertTrue(target_template.is_file(), "workspace-seed/templates/target.yaml no existe")

        # Debe cargarse y validarse mediante scope_validator
        target_data = scope_validator.load_target_yaml(target_template)
        self.assertIn("scope", target_data)
        self.assertIn("in_scope", target_data["scope"])
        self.assertIn("out_of_scope", target_data["scope"])
        self.assertIn("domains", target_data["scope"]["in_scope"])
        self.assertIn("ips", target_data["scope"]["in_scope"])
        self.assertIn("cidrs", target_data["scope"]["in_scope"])
        self.assertIn("operational_limits", target_data)

        # 2. Validar normalizacion y extraccion de objetivos
        self.assertEqual(scope_validator.normalize_target("https://api.example.com/v1/auth"), "api.example.com")
        self.assertEqual(scope_validator.normalize_target("HTTP://Test.Org:8080/path?arg=1"), "test.org")
        self.assertEqual(scope_validator.normalize_target("192.0.2.1:443"), "192.0.2.1")
        self.assertEqual(scope_validator.normalize_target("admin.internal.net"), "admin.internal.net")

        # 3. Validar coincidencia de dominios (exacto y wildcards)
        self.assertTrue(scope_validator.domain_matches("example.com", "example.com"))
        self.assertTrue(scope_validator.domain_matches("sub.example.com", "*.example.com"))
        self.assertTrue(scope_validator.domain_matches("deep.sub.example.com", "*.example.com"))
        self.assertFalse(scope_validator.domain_matches("notexample.com", "*.example.com"))
        self.assertFalse(scope_validator.domain_matches("example.org", "example.com"))

        # 4. Validar decisiones de scope y precedencia de exclusion
        # In-scope directo
        verdict, _ = scope_validator.check_scope("example.com", target_data)
        self.assertEqual(verdict, "IN_SCOPE")

        # In-scope wildcard
        verdict, _ = scope_validator.check_scope("api.example.com", target_data)
        self.assertEqual(verdict, "IN_SCOPE")

        # Out-of-scope directo
        verdict, _ = scope_validator.check_scope("payments.example.com", target_data)
        self.assertEqual(verdict, "OUT_OF_SCOPE")

        # Out-of-scope URL compleja
        verdict, _ = scope_validator.check_scope("https://payments.example.com/v1/checkout", target_data)
        self.assertEqual(verdict, "OUT_OF_SCOPE")

        # IP in-scope por CIDR
        verdict, _ = scope_validator.check_scope("192.0.2.50", target_data)
        self.assertEqual(verdict, "IN_SCOPE")

        # IP excluida explicitamente a pesar de pertenecer al CIDR in-scope (precedencia de exclusion)
        verdict, _ = scope_validator.check_scope("192.0.2.254", target_data)
        self.assertEqual(verdict, "OUT_OF_SCOPE")

        # Objetivo desconocido / no listado
        verdict, _ = scope_validator.check_scope("unauthorized.com", target_data)
        self.assertEqual(verdict, "UNKNOWN")

        # 5. Validar integracion en Dockerfile y plugin Zsh
        dockerfile = (REPO_ROOT / "images" / "full" / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("pt-scope-validator", dockerfile)

        plugin = (REPO_ROOT / "shell" / "pentest-lab" / "pentest-lab.plugin.zsh").read_text(encoding="utf-8")
        self.assertIn("_pt-scope-script()", plugin)
        self.assertIn("_pt-scope-resolve-config()", plugin)
        self.assertIn("_pt-eng-help()", plugin)
        self.assertIn("pt-eng()", plugin)
        self.assertIn("pt-scope()", plugin)

    def test_finding_manager_and_report_compiler(self):
        """Verifica la plantilla evidence.md, compilador de reportes y linter Evidence-First."""
        # 1. Validar plantilla de evidencia
        evidence_tmpl = REPO_ROOT / "workspace-seed" / "templates" / "evidence.md"
        self.assertTrue(evidence_tmpl.is_file(), "workspace-seed/templates/evidence.md no existe")

        parsed = report_compiler.parse_evidence_file(evidence_tmpl)
        self.assertEqual(parsed["id"], "VULN-01")
        self.assertEqual(parsed["severity"], "HIGH")
        self.assertEqual(parsed["cvss_score"], 6.5)
        self.assertEqual(parsed["cwe"], "CWE-639")
        self.assertTrue(parsed["has_poc"])
        self.assertTrue(parsed["has_remediation"])

        # 2. Validar compilación y linting en un engagement simulado
        import tempfile, shutil
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = pathlib.Path(tmp_dir)
            ev_dir = tmp / "evidence"
            ev_dir.mkdir()
            shutil.copy(evidence_tmpl, ev_dir / "VULN-01.md")
            target_yaml = REPO_ROOT / "workspace-seed" / "templates" / "target.yaml"
            shutil.copy(target_yaml, tmp / "target.yaml")

            # Comprobar check_findings en estado saludable
            ok, issues = report_compiler.check_findings(tmp)
            self.assertTrue(ok)

            # Comprobar compilación de REPORT.md
            report_out = report_compiler.build_report(tmp)
            self.assertTrue(report_out.is_file())
            content = report_out.read_text(encoding="utf-8")
            self.assertIn("# Informe de Auditoría de Seguridad:", content)
            self.assertIn("## 1. Resumen Ejecutivo", content)
            self.assertIn("## 2. Alcance y Límites Operacionales", content)
            self.assertIn("## 3. Matriz Consolidada de Hallazgos", content)
            self.assertIn("## 4. Detalle Técnico de Hallazgos", content)
            self.assertIn("VULN-01", content)
            self.assertIn("CWE-639", content)

            # Comprobar detección de activo fuera de alcance
            vuln_file = ev_dir / "VULN-01.md"
            vuln_file.write_text(vuln_file.read_text().replace("https://api.example.com/v1/users/1234/profile", "https://payments.example.com/checkout"))
            ok_bad, issues_bad = report_compiler.check_findings(tmp)
            self.assertFalse(ok_bad)
            self.assertTrue(any("FUERA DE ALCANCE" in msg for msg in issues_bad))

        # 3. Validar integración en Dockerfile y plugin Zsh
        dockerfile = (REPO_ROOT / "images" / "full" / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("pt-report-compiler", dockerfile)

        plugin = (REPO_ROOT / "shell" / "pentest-lab" / "pentest-lab.plugin.zsh").read_text(encoding="utf-8")
        self.assertIn("_pt-report-script()", plugin)
        self.assertIn("_pt-finding-help()", plugin)
        self.assertIn("pt-finding()", plugin)
        self.assertIn("_pt-report-help()", plugin)
        self.assertIn("pt-report()", plugin)

    def test_ssrf_injection_audit_and_callback_helper(self):
        """Verifica la skill ssrf-injection-audit, prompt de inyección y helper pt-callback."""
        # 1. Validar skill y sincronización
        skill_src = REPO_ROOT / "skills" / "ssrf-injection-audit" / "SKILL.md"
        skill_seed = REPO_ROOT / "workspace-seed" / "skills" / "ssrf-injection-audit" / "SKILL.md"
        self.assertTrue(skill_src.is_file(), "skills/ssrf-injection-audit/SKILL.md no existe")
        self.assertTrue(skill_seed.is_file(), "workspace-seed/skills/ssrf-injection-audit/SKILL.md no existe")
        self.assertEqual(skill_src.read_text(encoding="utf-8"), skill_seed.read_text(encoding="utf-8"))

        content = skill_src.read_text(encoding="utf-8")
        self.assertIn("name: ssrf-injection-audit", content)
        self.assertIn("category: injection", content)
        self.assertIn("pt-callback", content)
        self.assertIn("## 1. Propósito y Alcance", content)
        self.assertIn("## 2. Precondiciones y Guardrails", content)
        self.assertIn("## 3. Flujo de Ejecución", content)

        # 2. Validar prompt template de agente
        prompt_src = REPO_ROOT / "skills" / "prompts" / "injection-agent.prompt.md"
        prompt_seed = REPO_ROOT / "workspace-seed" / "templates" / "prompts" / "injection-agent.prompt.md"
        self.assertTrue(prompt_src.is_file())
        self.assertTrue(prompt_seed.is_file())
        self.assertEqual(prompt_src.read_text(encoding="utf-8"), prompt_seed.read_text(encoding="utf-8"))

        # 3. Validar helper pt-callback en plugin Zsh
        plugin = (REPO_ROOT / "shell" / "pentest-lab" / "pentest-lab.plugin.zsh").read_text(encoding="utf-8")
        self.assertIn("pt-callback()", plugin)
        self.assertIn("alias ptcallback=", plugin)
        self.assertIn("alias callback=", plugin)
        self.assertIn("/tmp/seclab-callback.log", plugin)
        self.assertIn("/tmp/seclab-callback.pid", plugin)

    def test_agent_context_aggregator(self):
        """Verifica la agregación determinista de contexto (pt-context) para agentes."""
        import shutil
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = pathlib.Path(tmp_dir)

            # 1. Crear estructura de engagement
            target_tmpl = REPO_ROOT / "workspace-seed" / "templates" / "target.yaml"
            shutil.copy(target_tmpl, tmp / "target.yaml")

            recon_dir = tmp / "recon"
            recon_dir.mkdir()
            (recon_dir / "live_hosts.txt").write_text("https://api.example.com\nhttps://admin.example.com\n", encoding="utf-8")
            (recon_dir / "subdomains.txt").write_text("api.example.com\nadmin.example.com\napp.example.com\n", encoding="utf-8")
            (recon_dir / "urls_all.txt").write_text("https://api.example.com/v1/auth\nhttps://api.example.com/v1/users\n", encoding="utf-8")
            (recon_dir / "js_files.txt").write_text("https://api.example.com/main.js\n", encoding="utf-8")

            patterns_dir = recon_dir / "patterns"
            patterns_dir.mkdir()
            (patterns_dir / "idor.txt").write_text("https://api.example.com/v1/users/123\n", encoding="utf-8")

            ev_dir = tmp / "evidence"
            ev_dir.mkdir()
            ev_tmpl = REPO_ROOT / "workspace-seed" / "templates" / "evidence.md"
            shutil.copy(ev_tmpl, ev_dir / "VULN-01.md")

            term_log = tmp / "terminal.log"
            term_log.write_text(
                "tmux session started\n"
                ">>> [2026-10-04T12:00:00+00:00] [AUDIT-MARK] VULN-01: Confirmado IDOR en perfil <<<\n"
                "command execution completed\n",
                encoding="utf-8",
            )

            # 2. Validar recolección de datos
            scope_data = agent_context.load_scope_data(tmp)
            self.assertEqual(scope_data["engagement"]["name"], "example-engagement")
            self.assertIn("example.com", scope_data["scope"]["in_scope"]["domains"])

            recon_summary = agent_context.collect_recon_summary(tmp)
            self.assertEqual(len(recon_summary["live_hosts"]), 2)
            self.assertEqual(recon_summary["subdomains_count"], 3)
            self.assertEqual(recon_summary["urls_count"], 2)
            self.assertEqual(recon_summary["js_files_count"], 1)
            self.assertEqual(recon_summary["patterns"].get("idor"), 1)

            findings = agent_context.collect_findings(tmp)
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0]["id"], "VULN-01")
            self.assertEqual(findings[0]["severity"], "HIGH")

            lines, size_str, marks = agent_context.collect_audit_marks(tmp)
            self.assertEqual(lines, 3)
            self.assertEqual(len(marks), 1)
            self.assertIn("VULN-01", marks[0])

            # 3. Validar resolución de skills y prompts
            auth_skill = agent_context.resolve_skill_or_prompt("auth")
            self.assertIsNotNone(auth_skill)
            self.assertEqual(auth_skill["type"], "skill")
            self.assertEqual(auth_skill["category"], "auth")

            auth_prompt = agent_context.resolve_skill_or_prompt("auth-agent")
            self.assertIsNotNone(auth_prompt)
            self.assertEqual(auth_prompt["type"], "prompt")
            self.assertIn("auth-agent.prompt.md", auth_prompt["name"])

            logic_prompt = agent_context.resolve_skill_or_prompt("logic-agent")
            self.assertIsNotNone(logic_prompt)
            self.assertEqual(logic_prompt["type"], "prompt")
            self.assertIn("logic-agent.prompt.md", logic_prompt["name"])

            # 4. Validar construcción de contexto dict y render Markdown
            ctx_dict = agent_context.generate_context_dict(tmp, "auth-agent")
            self.assertEqual(ctx_dict["engagement"]["name"], "example-engagement")
            self.assertEqual(ctx_dict["findings"]["total"], 1)
            self.assertEqual(ctx_dict["findings"]["severity_counts"]["HIGH"], 1)
            self.assertIn("active_skill", ctx_dict)
            self.assertIn("coverage", ctx_dict)
            self.assertGreater(ctx_dict["coverage"]["coverage_score"], 0)

            md = agent_context.format_markdown_context(ctx_dict)
            self.assertIn("# Contexto de Seguridad del Agente: example-engagement", md)
            self.assertIn("## 1. Alcance y Reglas de Compromiso", md)
            self.assertIn("## 2. Cobertura Metodológica & Checklist", md)
            self.assertIn("## 3. Superficie de Ataque y Reconocimiento", md)
            self.assertIn("## 4. Matriz de Hallazgos Validados", md)
            self.assertIn("## 5. Trazabilidad de Auditoría", md)
            self.assertIn("## 6. Directivas de Agente: auth-agent.prompt.md", md)
            self.assertIn("VULN-01", md)

            # 5. Validar integración en Dockerfile y plugin Zsh
            dockerfile = (REPO_ROOT / "images" / "full" / "Dockerfile").read_text(encoding="utf-8")
            self.assertIn("pt-agent-context", dockerfile)

            plugin = (REPO_ROOT / "shell" / "pentest-lab" / "pentest-lab.plugin.zsh").read_text(encoding="utf-8")
            self.assertIn("_pt-context-script()", plugin)
            self.assertIn("_pt-context-help()", plugin)
            self.assertIn("pt-context()", plugin)

    def test_engagement_packaging_and_lifecycle_closure(self):
        """Verifica la sanitización, empaquetado reproducible con SHA-256 y cierre de engagements."""
        import shutil
        import tarfile
        import tempfile

        # 1. Validar motor de sanitización
        dummy_jwt = "eyJ" + "hbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9." + "eyJ" + "zdWIiOiIxMjM0NTY3ODkwIn0." + "abcdef1234567890"
        dirty_text = (
            "curl -u tester:SuperSecretPassword123! https://admin:pass456@api.target.com/v1 "
            f"-H 'Authorization: Bearer {dummy_jwt}' "
            "-H 'Cookie: session=sess_987654321; other=public'\n"
            "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA...\n-----END RSA PRIVATE KEY-----\n"
        )
        clean_text, count = engagement_packer.sanitize_text(dirty_text)
        self.assertGreaterEqual(count, 4)
        self.assertNotIn("SuperSecretPassword123!", clean_text)
        self.assertNotIn("pass456", clean_text)
        self.assertNotIn("sess_987654321", clean_text)
        self.assertIn("[REDACTED_PASSWORD]", clean_text)
        self.assertIn("[REDACTED_AUTH_TOKEN]", clean_text)
        self.assertIn("[REDACTED_SESSION]", clean_text)
        self.assertIn("[REDACTED_PRIVATE_KEY]", clean_text)

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = pathlib.Path(tmp_dir)

            # 2. Configurar estructura de engagement con credenciales sin sanitizar en evidencia
            target_tmpl = REPO_ROOT / "workspace-seed" / "templates" / "target.yaml"
            shutil.copy(target_tmpl, tmp / "target.yaml")
            scope_tmpl = REPO_ROOT / "workspace-seed" / "templates" / "scope.txt"
            shutil.copy(scope_tmpl, tmp / "scope.txt")

            ev_dir = tmp / "evidence"
            ev_dir.mkdir()
            ev_file = ev_dir / "VULN-01.md"
            ev_tmpl = REPO_ROOT / "workspace-seed" / "templates" / "evidence.md"
            ev_content = ev_tmpl.read_text(encoding="utf-8") + "\n```bash\n" + dirty_text + "\n```\n"
            ev_file.write_text(ev_content, encoding="utf-8")

            recon_dir = tmp / "recon"
            recon_dir.mkdir()
            (recon_dir / "live_hosts.txt").write_text("https://api.example.com\n", encoding="utf-8")

            # 3. Validar empaquetado con sanitización y manifiesto SHA-256
            out_tar = tmp / "exports" / "test_bundle.tar.gz"
            res = engagement_packer.pack_engagement(tmp, output_path=out_tar, sanitize=True, archive_format="tar.gz")

            self.assertEqual(res["status"], "success")
            self.assertEqual(res["engagement"], tmp.name)
            self.assertTrue(out_tar.is_file())
            self.assertGreater(res["archive_size"], 0)
            self.assertGreaterEqual(res["redactions_count"], 4)
            self.assertEqual(len(res["archive_sha256"]), 64)

            # Verificar contenido del tarball y el manifest.sha256
            with tarfile.open(out_tar, "r:gz") as tf:
                names = tf.getnames()
                self.assertTrue(any("manifest.sha256" in n for n in names))
                self.assertTrue(any("REPORT.md" in n for n in names))
                self.assertTrue(any("target.yaml" in n for n in names))
                self.assertTrue(any("evidence/VULN-01.md" in n for n in names))

                # Extraer y verificar que la evidencia dentro del tarball esté sanitizada
                san_ev = tf.extractfile(f"{tmp.name}/evidence/VULN-01.md").read().decode("utf-8")
                self.assertNotIn("SuperSecretPassword123!", san_ev)
                self.assertIn("[REDACTED_PASSWORD]", san_ev)

                # Verificar integridad de los hashes en manifest.sha256
                manifest_content = tf.extractfile(f"{tmp.name}/manifest.sha256").read().decode("utf-8")
                for line in manifest_content.splitlines():
                    if line.strip():
                        hash_val, rel_p = line.split("  ", 1)
                        self.assertEqual(len(hash_val), 64)

            # 4. Validar cierre formal de auditoría
            close_res = engagement_packer.close_engagement(tmp)
            self.assertEqual(close_res["status"], "closed")
            self.assertTrue(close_res["target_yaml_updated"])

            target_updated = (tmp / "target.yaml").read_text(encoding="utf-8")
            self.assertIn("status: closed", target_updated)
            self.assertIn("closed_at:", target_updated)

            # 5. Validar integración en Dockerfile y plugin Zsh
            dockerfile = (REPO_ROOT / "images" / "full" / "Dockerfile").read_text(encoding="utf-8")
            self.assertIn("pt-engagement-packer", dockerfile)

            plugin = (REPO_ROOT / "shell" / "pentest-lab" / "pentest-lab.plugin.zsh").read_text(encoding="utf-8")
            self.assertIn("_pt-packer-script()", plugin)
            self.assertIn("pack)", plugin)
            self.assertIn("close)", plugin)
            self.assertIn("alias ptpack=", plugin)
            self.assertIn("alias engpack=", plugin)
            self.assertIn("alias ptclose=", plugin)

    def test_recon_pipeline_with_scope_guard(self):
        """Verifica el pipeline determinista de reconocimiento con Scope Guard integrado."""
        import json
        import shutil
        import tempfile

        # 1. Normalización y verificación de alcance
        self.assertEqual(recon_pipeline.normalize_target("https://api.acme.corp:8443/v1/users"), "api.acme.corp")
        self.assertEqual(recon_pipeline.normalize_target("admin.internal.net"), "admin.internal.net")

        scope_rules = {
            "scope": {
                "in_scope": {
                    "domains": ["acme.corp", "*.acme.corp"],
                    "ips": ["192.168.1.50"],
                    "cidrs": ["10.0.0.0/24"],
                },
                "out_of_scope": {
                    "domains": ["admin.acme.corp", "*.internal.acme.corp"],
                    "ips": ["192.168.1.1"],
                },
            }
        }

        # Verificación positiva en alcance
        verdict, _ = recon_pipeline.check_scope("acme.corp", scope_rules)
        self.assertEqual(verdict, "IN_SCOPE")
        verdict, _ = recon_pipeline.check_scope("api.acme.corp", scope_rules)
        self.assertEqual(verdict, "IN_SCOPE")
        verdict, _ = recon_pipeline.check_scope("192.168.1.50", scope_rules)
        self.assertEqual(verdict, "IN_SCOPE")

        # Verificación de exclusiones (OUT_OF_SCOPE gana siempre)
        verdict, reason = recon_pipeline.check_scope("admin.acme.corp", scope_rules)
        self.assertEqual(verdict, "OUT_OF_SCOPE")
        self.assertIn("admin.acme.corp", reason)

        verdict, reason = recon_pipeline.check_scope("db.internal.acme.corp", scope_rules)
        self.assertEqual(verdict, "OUT_OF_SCOPE")

        verdict, _ = recon_pipeline.check_scope("192.168.1.1", scope_rules)
        self.assertEqual(verdict, "OUT_OF_SCOPE")

        # Desconocido fuera de alcance explícito
        verdict, _ = recon_pipeline.check_scope("evil.com", scope_rules)
        self.assertEqual(verdict, "UNKNOWN")

        # 2. Ejecución simulada (dry_run) del pipeline completo en un engagement temporal
        with tempfile.TemporaryDirectory() as tmpdir:
            eng_path = pathlib.Path(tmpdir) / "engagements" / "test-target"
            eng_path.mkdir(parents=True)

            target_yaml_content = (
                "engagement:\n"
                "  name: test-target\n"
                "  status: active\n"
                "scope:\n"
                "  in_scope:\n"
                "    domains:\n"
                "      - test-target.com\n"
                "      - '*.test-target.com'\n"
                "  out_of_scope:\n"
                "    domains:\n"
                "      - admin.test-target.com\n"
                "      - '*.internal.test-target.com'\n"
            )
            (eng_path / "target.yaml").write_text(target_yaml_content, encoding="utf-8")

            pipeline = recon_pipeline.ReconPipeline(eng_path, dry_run=True)
            res = pipeline.run_all(stage="all")

            self.assertIn("summary", res)
            summary = res["summary"]
            self.assertEqual(summary["engagement"], "test-target")
            self.assertEqual(summary["in_scope_domains"], ["test-target.com", "*.test-target.com"])

            # 3. Validar filtrado de subdominios
            sub_raw = [
                "test-target.com",
                "api.test-target.com",
                "admin.test-target.com",
                "portal.internal.test-target.com",
                "evil.com",
            ]
            valid_subs, discarded = pipeline.filter_domains_by_scope(sub_raw)
            self.assertIn("test-target.com", valid_subs)
            self.assertIn("api.test-target.com", valid_subs)
            self.assertNotIn("admin.test-target.com", valid_subs)
            self.assertNotIn("portal.internal.test-target.com", valid_subs)
            self.assertNotIn("evil.com", valid_subs)
            self.assertEqual(len(discarded), 3)

            # 4. Validar integración en Dockerfile y plugin Zsh
            dockerfile = (REPO_ROOT / "images" / "full" / "Dockerfile").read_text(encoding="utf-8")
            self.assertIn("pt-recon-pipeline", dockerfile)

            plugin = (REPO_ROOT / "shell" / "pentest-lab" / "pentest-lab.plugin.zsh").read_text(encoding="utf-8")
            self.assertIn("_pt-recon-script()", plugin)
            self.assertIn("_pt-recon-help()", plugin)
            self.assertIn("alias ptrecon=", plugin)
            self.assertIn("alias reconpipeline=", plugin)

    def test_audit_checklist_and_coverage_evaluator(self):
        """Verifica la matriz de cobertura metodológica y checklist de auditoría."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            eng_path = pathlib.Path(tmpdir) / "engagements" / "acme-corp"
            eng_path.mkdir(parents=True)

            # 1. Crear estructura parcial de engagement
            (eng_path / "target.yaml").write_text("engagement:\n  name: acme-corp\n  status: active\n", encoding="utf-8")
            recon_dir = eng_path / "recon"
            recon_dir.mkdir()
            (recon_dir / "subdomains.txt").write_text("api.acme.corp\nauth.acme.corp\n", encoding="utf-8")
            (recon_dir / "live_hosts.txt").write_text("https://api.acme.corp\nhttps://auth.acme.corp\n", encoding="utf-8")
            (recon_dir / "urls_all.txt").write_text("https://api.acme.corp/v1/users\n", encoding="utf-8")
            (recon_dir / "js_files.txt").write_text("https://api.acme.corp/bundle.js\n", encoding="utf-8")

            # 2. Agregar evidencia con IDOR verificado
            ev_dir = eng_path / "evidence"
            ev_dir.mkdir()
            (ev_dir / "VULN-01.md").write_text(
                "---\n"
                "title: 'IDOR en API de Usuarios'\n"
                "id: 'VULN-01'\n"
                "severity: 'High'\n"
                "cwe: 'CWE-639'\n"
                "status: 'Confirmado'\n"
                "---\n\n"
                "# [VULN-01] IDOR en API\n\n"
                "## 1. Resumen\nFalla en capa de autorizacion.\n\n"
                "## 2. Pasos Detallados de Reproducción (PoC)\n```bash\ncurl -i https://api.acme.corp/v1/users/999\n```\n\n"
                "## 3. Petición y Respuesta Crudas (Raw HTTP Evidence)\n```http\nHTTP/1.1 200 OK\n```\n",
                encoding="utf-8",
            )

            # 3. Evaluar checklist
            evaluator = audit_checklist.AuditChecklistEvaluator(eng_path)
            res = evaluator.evaluate()

            self.assertEqual(res["engagement"], "acme-corp")
            self.assertGreater(res["coverage_score"], 0)
            self.assertEqual(res["total_findings"], 1)
            self.assertEqual(res["findings_summary"]["verified"], 1)

            # Validar que recon y auth estén completados
            matrix_map = {row["id"]: row for row in res["matrix"]}
            self.assertEqual(matrix_map["recon"]["status"], "COMPLETED")
            self.assertEqual(matrix_map["auth"]["status"], "COMPLETED")
            self.assertIn("VULN-01", matrix_map["auth"]["findings"])
            self.assertEqual(matrix_map["client"]["status"], "IN_PROGRESS")

            # 4. Validar formato de salida visual y markdown
            term_out = audit_checklist.format_terminal_output(res)
            self.assertIn("acme-corp", term_out)
            self.assertIn("Checklist Metodológico", term_out)

            md_out = audit_checklist.format_markdown_output(res)
            self.assertIn("## Matriz de Cobertura Metodológica", md_out)
            self.assertIn("| 1 | Reconocimiento", md_out)

            # 5. Validar integración en Dockerfile y plugin Zsh
            dockerfile = (REPO_ROOT / "images" / "full" / "Dockerfile").read_text(encoding="utf-8")
            self.assertIn("pt-audit-checklist", dockerfile)

            plugin = (REPO_ROOT / "shell" / "pentest-lab" / "pentest-lab.plugin.zsh").read_text(encoding="utf-8")
            self.assertIn("_pt-checklist-script()", plugin)
            self.assertIn("_pt-checklist-help()", plugin)
            self.assertIn("pt-checklist()", plugin)
            self.assertIn("check|checklist|coverage)", plugin)
            self.assertIn("alias ptcheck=", plugin)
            alias_coverage = 'alias coverage="pt-checklist"'
            self.assertIn(alias_coverage, plugin)

    def test_context_coverage_and_closure_guard(self):
        """Verifica la integración de cobertura en pt-context y compuerta pre-cierre en pt-eng close."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            eng_path = pathlib.Path(tmpdir) / "engagements" / "guard-test"
            eng_path.mkdir(parents=True)

            # 1. Sembrar target.yaml con status activo
            target_file = eng_path / "target.yaml"
            target_file.write_text(
                "engagement:\n"
                "  name: guard-test\n"
                "  status: active\n"
                "scope:\n"
                "  in_scope:\n"
                "    domains:\n"
                "      - guard.test\n",
                encoding="utf-8",
            )

            # 2. Agregar un hallazgo no verificado (borrador)
            ev_dir = eng_path / "evidence"
            ev_dir.mkdir()
            (ev_dir / "draft-vuln.md").write_text(
                "---\n"
                "id: VULN-DRAFT-01\n"
                "title: Borrador de Vulnerabilidad Sin Confirmar\n"
                "status: Borrador\n"
                "severity: MEDIUM\n"
                "---\n\n"
                "# Borrador de prueba\n",
                encoding="utf-8",
            )

            # 3. Validar que close_engagement bloquea el cierre sin --force
            blocked_res = engagement_packer.close_engagement(eng_path, force=False)
            self.assertEqual(blocked_res["status"], "blocked")
            self.assertFalse(blocked_res["ready_for_closure"])
            self.assertGreater(len(blocked_res["blocking_issues"]), 0)
            self.assertTrue(any("sin verificar" in issue for issue in blocked_res["blocking_issues"]))

            # target.yaml NO debe haberse cerrado
            target_unmod = target_file.read_text(encoding="utf-8")
            self.assertNotIn("status: closed", target_unmod)

            # 4. Validar que close_engagement con force=True permite forzar el cierre
            forced_res = engagement_packer.close_engagement(eng_path, force=True)
            self.assertEqual(forced_res["status"], "closed")
            self.assertTrue(forced_res["forced"])
            self.assertIn("bypassed_issues", forced_res)

            target_closed = target_file.read_text(encoding="utf-8")
            self.assertIn("status: closed", target_closed)
            self.assertIn("closed_at:", target_closed)

            # 5. Restablecer target a active y corregir requisitos para cierre limpio
            target_file.write_text(
                "engagement:\n"
                "  name: guard-test\n"
                "  status: active\n"
                "scope:\n"
                "  in_scope:\n"
                "    domains:\n"
                "      - guard.test\n",
                encoding="utf-8",
            )
            # Confirmar el hallazgo
            (ev_dir / "draft-vuln.md").write_text(
                "---\n"
                "id: VULN-DRAFT-01\n"
                "title: Vulnerabilidad Confirmada\n"
                "status: Confirmado\n"
                "severity: MEDIUM\n"
                "---\n\n"
                "# Vulnerabilidad Confirmada\n",
                encoding="utf-8",
            )
            # Generar REPORT.md
            (eng_path / "REPORT.md").write_text("# Reporte Final de Auditoría\n", encoding="utf-8")

            # Ahora el cierre debe ser limpio sin force
            clean_res = engagement_packer.close_engagement(eng_path, force=False)
            self.assertEqual(clean_res["status"], "closed")
            self.assertFalse(clean_res["forced"])
            self.assertTrue(clean_res["target_yaml_updated"])

            # 6. Validar que pt-context ingesta correctamente la cobertura
            ctx = agent_context.generate_context_dict(eng_path)
            self.assertIn("coverage", ctx)
            self.assertIn("coverage_score", ctx["coverage"])
            self.assertIn("matrix", ctx["coverage"])
            self.assertTrue(ctx["coverage"]["ready_for_closure"])

            # 7. Validar opciones documentadas en plugin Zsh
            plugin = (REPO_ROOT / "shell" / "pentest-lab" / "pentest-lab.plugin.zsh").read_text(encoding="utf-8")
            self.assertIn("pt-eng close [nombre] [opciones]", plugin)
            self.assertIn("-f, --force", plugin)

    def test_methodology_next_step_recommender(self):
        """Verifica el recomendador de próximo paso metodológico y guía interactiva (pt-next)."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            eng_path = pathlib.Path(tmpdir) / "engagements" / "next-test"
            eng_path.mkdir(parents=True)

            # 1. Caso A: Directorio vacío -> Recomienda scope
            steps_scope = audit_next.determine_roadmap(eng_path)
            self.assertEqual(steps_scope[0]["id"], "scope")
            self.assertEqual(steps_scope[0]["discipline"], "recon")
            self.assertIn("target.yaml", steps_scope[0]["reason"])

            # 2. Caso B: target.yaml sembrado -> Recomienda recon
            target_file = eng_path / "target.yaml"
            target_file.write_text(
                "engagement:\n"
                "  name: next-test\n"
                "  status: active\n"
                "scope:\n"
                "  in_scope:\n"
                "    domains:\n"
                "      - next.test\n",
                encoding="utf-8",
            )
            steps_recon = audit_next.determine_roadmap(eng_path)
            self.assertEqual(steps_recon[0]["id"], "recon")
            self.assertEqual(steps_recon[0]["skill"], "recon-profiling")
            self.assertIn("pt-recon", steps_recon[0]["command"])

            # 3. Caso C: recon completado -> Recomienda fuzzing
            recon_dir = eng_path / "recon"
            recon_dir.mkdir()
            (recon_dir / "live_hosts.txt").write_text("https://next.test\n", encoding="utf-8")
            (recon_dir / "subdomains.txt").write_text("next.test\n", encoding="utf-8")

            steps_fuzz = audit_next.determine_roadmap(eng_path)
            self.assertEqual(steps_fuzz[0]["id"], "fuzzing")
            self.assertEqual(steps_fuzz[0]["skill"], "param-discovery")
            self.assertIn("pt-fuzz-params", steps_fuzz[0]["command"])

            # 4. Caso D: Hallazgo en borrador -> Recomienda verificación
            fuzz_dir = eng_path / "fuzzing"
            fuzz_dir.mkdir()
            (fuzz_dir / "params.txt").write_text("id\nuser\n", encoding="utf-8")

            ev_dir = eng_path / "evidence"
            ev_dir.mkdir()
            (ev_dir / "draft-vuln.md").write_text(
                "---\n"
                "id: VULN-DRAFT-01\n"
                "status: Borrador\n"
                "severity: HIGH\n"
                "---\n\n# Borrador\n",
                encoding="utf-8",
            )

            steps_draft = audit_next.determine_roadmap(eng_path)
            has_triage = any(s["id"] == "verify_findings" for s in steps_draft)
            self.assertTrue(has_triage)

            # 5. Validar generación de prompt para LLM y salida formateada
            prompt_out = audit_next.generate_llm_prompt(eng_path, steps_recon[0])
            self.assertIn("SYSTEM PROMPT", prompt_out)
            self.assertIn("next-test", prompt_out)
            self.assertIn("pt-scope show", prompt_out)

            term_out = audit_next.format_terminal_output(eng_path, steps_recon[0], steps_recon, show_all=True)
            self.assertIn("next-test", term_out)
            self.assertIn("Próximo Paso Recomendado", term_out)

            # 6. Validar integración en Dockerfile y plugin Zsh
            dockerfile = (REPO_ROOT / "images" / "full" / "Dockerfile").read_text(encoding="utf-8")
            self.assertIn("pt-next", dockerfile)

            plugin = (REPO_ROOT / "shell" / "pentest-lab" / "pentest-lab.plugin.zsh").read_text(encoding="utf-8")
            self.assertIn("_pt-next-script()", plugin)
            self.assertIn("_pt-next-help()", plugin)
            self.assertIn("pt-next()", plugin)
            self.assertIn("next)", plugin)
            self.assertIn("alias ptnext=", plugin)
            self.assertIn("alias engnext=", plugin)
            self.assertIn("alias next=", plugin)

    def test_interactive_help_system_and_operator_guide(self):
        """Verifica el centro de ayuda, guía del operador (pt-guide) y la interfaz interactiva HTML."""
        # 1. Comprobar resolución del archivo HTML de la guía
        html_path = guide_helper.resolver_guia_html()
        self.assertIsNotNone(html_path, "No se pudo resolver el archivo HTML de la guía")
        self.assertTrue(html_path.is_file(), f"El archivo {html_path} no existe")

        # 2. Validar contenido y secciones del archivo HTML
        html_content = html_path.read_text(encoding="utf-8")
        self.assertIn("SecLab-SBF", html_content)
        self.assertIn("Auditoría Web / API", html_content)
        self.assertIn("Reto CTF / Máquina", html_content)
        self.assertIn("Orquestar con IA / Agentes", html_content)
        self.assertIn("Pivoting & Redes", html_content)
        self.assertIn("Scope Guard", html_content)
        self.assertIn("pt-eng new", html_content)
        self.assertIn("pt-recon", html_content)
        self.assertIn("pt-next", html_content)
        self.assertIn("pt-checklist", html_content)
        self.assertIn("pt-finding", html_content)
        self.assertIn("pt-report", html_content)
        self.assertIn("pt-callback", html_content)
        self.assertIn("HERRAMIENTAS", html_content)

        # 3. Comprobar presencia de la guía en workspace-seed
        seed_guia = REPO_ROOT / "workspace-seed" / "guia.html"
        self.assertTrue(seed_guia.is_file(), "workspace-seed/guia.html no existe")
        self.assertEqual(seed_guia.read_text(encoding="utf-8"), html_content)

        # 4. Validar actualización en workspace-seed/README.md
        seed_readme = (REPO_ROOT / "workspace-seed" / "README.md").read_text(encoding="utf-8")
        self.assertIn("pt-guide", seed_readme)
        self.assertIn("guia.html", seed_readme)
        self.assertIn("pt-next", seed_readme)

        # 5. Validar estructura de las 8 disciplinas en pt-guide.py
        self.assertEqual(len(guide_helper.DISCIPLINAS), 8)
        expected_keys = {
            "recon-profiling",
            "param-discovery",
            "auth-matrix-audit",
            "business-logic-audit",
            "ssrf-injection-audit",
            "client-side-spa-audit",
            "api-security-audit",
            "triage-gatekeeper",
        }
        actual_keys = {d["key"] for d in guide_helper.DISCIPLINAS}
        self.assertEqual(expected_keys, actual_keys)

        for disc in guide_helper.DISCIPLINAS:
            self.assertIn("id", disc)
            self.assertIn("name", disc)
            self.assertIn("desc", disc)
            self.assertIn("cmd", disc)
            self.assertIn("tools", disc)
            self.assertIn("artifacts", disc)
            self.assertTrue(len(disc["tools"]) > 0)

        # 6. Validar integración en Dockerfile
        dockerfile = (REPO_ROOT / "images" / "full" / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("COPY scripts/pt-guide.py /usr/local/bin/pt-guide", dockerfile)
        self.assertIn("/usr/local/share/seclab/guide/index.html", dockerfile)
        self.assertIn("/usr/local/bin/pt-guide", dockerfile)

        # 7. Validar integración en plugin Zsh
        plugin = (REPO_ROOT / "shell" / "pentest-lab" / "pentest-lab.plugin.zsh").read_text(encoding="utf-8")
        self.assertIn("_pt-guide-script()", plugin)
        self.assertIn("_pt-guide-help()", plugin)
        self.assertIn("pt-guide()", plugin)
        self.assertIn("guide)", plugin)
        self.assertIn('alias ptguide="pt-guide"', plugin)
        self.assertIn('alias guia="pt-guide"', plugin)
        self.assertIn('alias guide="pt-guide"', plugin)
        self.assertIn('alias engguide="pt-eng guide"', plugin)
        self.assertIn("pt-guide", plugin)


class TestSecLabDashboardAndVault(unittest.TestCase):
    """Verifica la integridad del Dashboard Táctico, API Key Vault y pt-vault-bridge."""

    def test_vault_bridge_cli_integrity(self):
        bridge_path = REPO_ROOT / "scripts" / "pt-vault-bridge.py"
        self.assertTrue(bridge_path.exists(), "pt-vault-bridge.py debe existir")
        content = bridge_path.read_text(encoding="utf-8")
        self.assertIn("ENV_MAPPINGS", content)
        self.assertIn("cmd_run", content)
        self.assertIn("cmd_list", content)
        self.assertIn("cmd_get", content)
        # Verificar mapeo de proveedores esenciales
        self.assertIn("shodan", content)
        self.assertIn("censys", content)
        self.assertIn("virustotal", content)
        self.assertIn("chaos", content)
        self.assertIn("openai", content)
        self.assertIn("anthropic", content)
        self.assertIn("gemini", content)

    def test_pentest_lab_plugin_vault_integration(self):
        plugin_path = REPO_ROOT / "shell" / "pentest-lab" / "pentest-lab.plugin.zsh"
        content = plugin_path.read_text(encoding="utf-8")
        self.assertIn("_pt-vault-script()", content)
        self.assertIn("pt-vault()", content)
        self.assertIn('alias ptvault="pt-vault"', content)
        self.assertIn('alias vault="pt-vault"', content)

    def test_dashboard_backend_structure(self):
        backend_dir = REPO_ROOT / "dashboard" / "backend"
        self.assertTrue(backend_dir.is_dir())
        self.assertTrue((backend_dir / "app" / "main.py").exists())
        self.assertTrue((backend_dir / "app" / "config.py").exists())
        self.assertTrue((backend_dir / "app" / "core" / "security.py").exists())
        self.assertTrue((backend_dir / "app" / "core" / "database.py").exists())
        self.assertTrue((backend_dir / "app" / "services" / "vault_service.py").exists())
        self.assertTrue((backend_dir / "app" / "services" / "proxy_service.py").exists())
        self.assertTrue((backend_dir / "app" / "api" / "endpoints" / "reports.py").exists())
        self.assertTrue((backend_dir / "app" / "api" / "endpoints" / "copilot.py").exists())

    def test_dashboard_makefile_targets(self):
        makefile_path = REPO_ROOT / "Makefile"
        content = makefile_path.read_text(encoding="utf-8")
        self.assertIn("dashboard-build:", content)
        self.assertIn("dashboard:", content)
        self.assertIn("dashboard-up:", content)
        self.assertIn("dashboard-daemon:", content)
        self.assertIn("dashboard-stop:", content)
        self.assertIn("dashboard-status:", content)

    def test_dashboard_loot_and_terminal_views(self):
        backend_dir = REPO_ROOT / "dashboard" / "backend"
        self.assertTrue((backend_dir / "app" / "api" / "endpoints" / "loot.py").exists())
        frontend_views = REPO_ROOT / "dashboard" / "frontend" / "src" / "views"
        self.assertTrue((frontend_views / "TerminalView.vue").exists())

    def test_dashboard_vpn_and_recon_services(self):
        backend_dir = REPO_ROOT / "dashboard" / "backend"
        self.assertTrue((backend_dir / "app" / "services" / "vpn_service.py").exists())
        self.assertTrue((backend_dir / "app" / "services" / "recon_service.py").exists())
        self.assertTrue((backend_dir / "app" / "api" / "endpoints" / "vpn.py").exists())
        self.assertTrue((backend_dir / "app" / "api" / "endpoints" / "recon.py").exists())

        # Verificar router registra vpn y recon
        router_file = backend_dir / "app" / "api" / "router.py"
        content = router_file.read_text(encoding="utf-8")
        self.assertIn("protected.include_router(vpn.router)", content)
        self.assertIn("protected.include_router(recon.router)", content)

        # Cargar y probar vpn_service
        sys.path.insert(0, str(backend_dir))
        try:
            from app.services.vpn_service import vpn_service
            self.assertEqual(vpn_service.canonical_profile("try"), "tryhackme")
            self.assertEqual(vpn_service.canonical_profile("THM"), "tryhackme")
            self.assertEqual(vpn_service.canonical_profile("htb"), "hackthebox")
            self.assertEqual(vpn_service.canonical_profile("client"), "client")
            self.assertIsNone(vpn_service.canonical_profile("prohibited_vpn"))

            status = vpn_service.get_vpn_status()
            self.assertIn("connected", status)
            self.assertIn("profile", status)
            self.assertIn("interface", status)
            self.assertEqual(status["interface"], "tun0")

            # Conectar perfil inválido debe fallar controladamente
            res = vpn_service.connect("invalid_xyz")
            self.assertFalse(res["success"])
            self.assertIn("no autorizado", res["message"])

            saved = vpn_service.list_saved_profiles()
            self.assertIn("client", saved)
            self.assertIn("tryhackme", saved)
            self.assertIn("hackthebox", saved)
        finally:
            if str(backend_dir) in sys.path:
                sys.path.remove(str(backend_dir))

        # Verificar endpoint de descarga en reports.py y documentación
        reports_file = backend_dir / "app" / "api" / "endpoints" / "reports.py"
        content_rep = reports_file.read_text(encoding="utf-8")
        self.assertIn("download_engagement", content_rep)
        self.assertTrue((REPO_ROOT / "docs" / "dashboard.md").is_file())

    def test_dashboard_recon_service_logic(self):
        backend_dir = REPO_ROOT / "dashboard" / "backend"
        sys.path.insert(0, str(backend_dir))
        try:
            from app.services.recon_service import recon_service
            self.assertIsNone(recon_service.get_target_dir("nonexistent_engagement_12345"))
            status = recon_service.get_status("nonexistent_engagement_12345")
            self.assertIn("error", status)
        finally:
            if str(backend_dir) in sys.path:
                sys.path.remove(str(backend_dir))


class TestDashboardVpnOperations(unittest.TestCase):
    def setUp(self):
        backend_dir = str(REPO_ROOT / "dashboard" / "backend")
        sys.path.insert(0, backend_dir)
        try:
            from app.services import vpn_service
            self.module = vpn_service
            self.service = vpn_service.VpnService()
        finally:
            sys.path.remove(backend_dir)

    def test_installed_controller_and_credentials_use_child_environment(self):
        with patch.object(pathlib.Path, "is_file", return_value=True):
            service = self.module.VpnService()
        self.assertEqual(service.vpn_control_script, pathlib.Path("/usr/local/bin/vpn-control"))
        completed = self.module.subprocess.CompletedProcess([], 0, "VPN conectada", "")
        with patch.object(pathlib.Path, "exists", return_value=True), \
             patch.dict(os.environ, {"VPN_AUTH_USER": "inherited", "VPN_AUTH_PASSWORD": "inherited"}), \
             patch.object(self.module.subprocess, "run", return_value=completed) as run:
            result = service._execute_vpn_control("connect", "client", ("operator", " demo-password "))
            self.assertTrue(result["success"])
            command = run.call_args.args[0]
            self.assertEqual(command[1:], ["/usr/local/bin/vpn-control", "client", "connect", "client"])
            self.assertNotIn(" demo-password ", command)
            self.assertEqual(run.call_args.kwargs["env"]["VPN_AUTH_PASSWORD"], " demo-password ")
            self.assertEqual(os.environ["VPN_AUTH_PASSWORD"], "inherited")
            service._execute_vpn_control("disconnect")
            self.assertNotIn("VPN_AUTH_PASSWORD", run.call_args.kwargs["env"])

    def test_status_uses_daemon_and_does_not_treat_persistent_tun_as_connected(self):
        cases = [
            ("active=tryhackme\npid=123 running", "192.0.2.10", True, False, "tryhackme"),
            ("active=tryhackme\npid=123 running", None, False, True, "tryhackme"),
            ("active=none", "192.0.2.10", False, False, "none"),
            ("active=tryhackme stale\npid=missing", "192.0.2.10", False, False, "none"),
        ]
        for stdout, ip, connected, connecting, profile in cases:
            with self.subTest(stdout=stdout, ip=ip), \
                 patch.object(pathlib.Path, "is_socket", return_value=True), \
                 patch.object(pathlib.Path, "read_text", side_effect=PermissionError), \
                 patch.object(self.service, "get_tun0_ip", return_value=ip), \
                 patch.object(self.service, "_execute_vpn_control", return_value={"success": True, "stdout": stdout}) as control:
                status = self.service.get_vpn_status()
                control.assert_called_once_with("status")
                self.assertEqual(status["connected"], connected)
                self.assertEqual(status["connecting"], connecting)
                self.assertEqual(status["profile"], profile)
                self.assertEqual(status["ip"], ip if connected else None)

    def test_saved_credentials_reach_daemon_without_writing_root_state(self):
        saved = {"username": "operator", "password": " demo-password "}
        completed = {"success": True, "stdout": "VPN conectada", "stderr": ""}
        with patch.object(self.service, "get_saved_credentials", return_value=saved), \
             patch.object(pathlib.Path, "write_text", side_effect=AssertionError("No escribir .auth desde el dashboard")), \
             patch.object(self.service, "_execute_vpn_control", return_value=completed) as control:
            self.assertTrue(self.service.connect("cli")["success"])
            control.assert_called_once_with("connect", "client", ("operator", " demo-password "))
            control.reset_mock()
            self.assertTrue(self.service.connect("client", username="operator")["success"])
            control.assert_called_once_with("connect", "client", ("operator", " demo-password "))

    def test_invalid_credentials_never_start_or_switch_vpn(self):
        with patch.object(self.service, "get_saved_credentials", return_value=None), \
             patch.object(self.service, "_execute_vpn_control") as control:
            for action in (self.service.connect, self.service.switch):
                for username, password in (("operator", None), ("operator", "bad\nvalue"), ("operator", "bad\x00value"), ("operator", "x" * 257)):
                    with self.subTest(action=action.__name__, username=username):
                        self.assertFalse(action("client", username, password)["success"])
            control.assert_not_called()


def main():
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    recon_safety = load_module('recon_safety_tests', REPO_ROOT / 'scripts' / 'verify' / 'test_recon_safety.py')
    suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(recon_safety))
    build_inputs = load_module('build_inputs_tests', REPO_ROOT / 'scripts' / 'verify' / 'test_build_inputs.py')
    suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(build_inputs))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if result.wasSuccessful():
        print("python_units_check=ok")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
