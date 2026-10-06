#!/usr/bin/env python3
"""Centro de Ayuda y Guía del Operador de SecLab-SBF (pt-guide).

Proporciona asistencia integral, visual y táctica para que cualquier operador
o auditor que ingrese al contenedor sepa exactamente qué pasos seguir, qué
herramientas ejecutar y cómo orquestar engagements, retos CTF y agentes LLM.

Funcionalidades:
  1. Guía de terminal interactiva con flujos paso a paso y comandos listos.
  2. Servidor web embebido (--web / -w) para abrir la guía interactiva HTML.
  3. Asistente interactivo (--wizard / -i) para generar secuencias de comandos.
  4. Detalle táctico por disciplina metodológica (--discipline 1-8).
  5. Salida estructurada machine-readable (--json).

Sin dependencias externas (Python 3 stdlib).
"""

import argparse
import http.server
import json
import os
import pathlib
import shutil
import socketserver
import sys
import tempfile
import threading
from typing import Any, Dict, List, Optional, Tuple

# Colores ANSI respetando NO_COLOR y TERM=dumb
NO_COLOR = bool(os.environ.get("NO_COLOR")) or os.environ.get("TERM") == "dumb"
C_RESET = "" if NO_COLOR else "\033[0m"
C_BOLD = "" if NO_COLOR else "\033[1m"
C_RED = "" if NO_COLOR else "\033[31m"
C_GREEN = "" if NO_COLOR else "\033[32m"
C_YELLOW = "" if NO_COLOR else "\033[33m"
C_BLUE = "" if NO_COLOR else "\033[34m"
C_MAGENTA = "" if NO_COLOR else "\033[35m"
C_CYAN = "" if NO_COLOR else "\033[36m"
C_GRAY = "" if NO_COLOR else "\033[90m"

# Rutas estándar de búsqueda de la guía HTML. La copia instalada en
# /usr/local/share/seclab/guide/ (solo lectura, sin datos de engagements)
# se prueba antes que /workspace/guia.html a propósito: iniciar_servidor_web()
# aísla igualmente el archivo servido en cualquier caso (ver
# preparar_directorio_servido), pero preferir la copia instalada evita
# depender de esa segunda capa cuando ambas existen.
GUIDE_HTML_CANDIDATES = [
    pathlib.Path("/usr/local/share/seclab/guide/index.html"),
    pathlib.Path("/usr/local/share/seclab/guide/guia.html"),
    pathlib.Path(__file__).resolve().parent.parent / "docs" / "guia-laboratorio.html",
    pathlib.Path(__file__).resolve().parent.parent / "workspace-seed" / "guia.html",
    pathlib.Path("docs/guia-laboratorio.html"),
    pathlib.Path("workspace-seed/guia.html"),
    pathlib.Path("/workspace/guia.html"),
]

DISCIPLINAS: List[Dict[str, Any]] = [
    {
        "id": 1,
        "key": "recon-profiling",
        "name": "Reconocimiento Pasivo y Activo",
        "desc": "Descubrimiento de subdominios, tecnologías, certificados y superficie expuesta.",
        "cmd": "pt-recon <engagement>",
        "tools": ["assetfinder", "findomain", "httprobe", "gau"],
        "artifacts": ["recon/subdomains.txt", "recon/alive_hosts.txt", "notes/recon_summary.md"]
    },
    {
        "id": 2,
        "key": "param-discovery",
        "name": "Descubrimiento de Parámetros y Endpoints",
        "desc": "Fuzzing de parámetros ocultos, endpoints pasivos y parsing de APIs.",
        "cmd": "pt-fuzz-params <url>",
        "tools": ["x8", "gau", "qsreplace"],
        "artifacts": ["recon/params.json", "recon/endpoints.txt"]
    },
    {
        "id": 3,
        "key": "auth-matrix-audit",
        "name": "Autenticación y Matriz de Autorización",
        "desc": "Auditoría de roles, IDORs, bypass de autenticación, JWT y fallos de sesión.",
        "cmd": "pt-skills auth-matrix-audit",
        "tools": ["curl", "jwt-tool", "proxychains4"],
        "artifacts": ["evidence/auth-matrix.md", "notes/roles.md"]
    },
    {
        "id": 4,
        "key": "business-logic-audit",
        "name": "Lógica de Negocio y Flujos Críticos",
        "desc": "Condiciones de carrera, alteración de cantidades/precios y flujos de estado.",
        "cmd": "pt-skills business-logic-audit",
        "tools": ["turbo-intruder", "curl", "python3"],
        "artifacts": ["evidence/logic-flaw.md"]
    },
    {
        "id": 5,
        "key": "ssrf-injection-audit",
        "name": "Inyecciones y SSRF con Validación OOB",
        "desc": "SQLi, SSRF, SSTI y Command Injection verificados con servidor de callbacks local.",
        "cmd": "pt-callback listen 9001",
        "tools": ["pt-callback", "sqlmap", "commix", "dalfox"],
        "artifacts": ["evidence/ssrf-oob.md", "evidence/sqli.md"]
    },
    {
        "id": 6,
        "key": "client-side-spa-audit",
        "name": "Cliente y SPAs (Single Page Applications)",
        "desc": "DOM XSS, fugas de secretos en bundles JS, postMessage y CSP bypass.",
        "cmd": "pt-skills client-side-spa-audit",
        "tools": ["dalfox", "gf", "zsteg"],
        "artifacts": ["evidence/xss-stored.md"]
    },
    {
        "id": 7,
        "key": "api-security-audit",
        "name": "Seguridad de APIs, GraphQL y Microservicios",
        "desc": "Mass assignment, fallos de esquema, rate limiting y GraphQL introspection.",
        "cmd": "pt-skills api-security-audit",
        "tools": ["curl", "jq", "x8"],
        "artifacts": ["evidence/api-mass-assignment.md"]
    },
    {
        "id": 8,
        "key": "triage-gatekeeper",
        "name": "Triage, Severidad CVSS y Cierre",
        "desc": "Descarte de falsos positivos, scoring CVSS v3.1, reporte y compuerta pre-cierre.",
        "cmd": "pt-report compile && pt-eng close",
        "tools": ["pt-finding", "pt-report", "pt-checklist", "pt-eng"],
        "artifacts": ["reports/report.md", "dist/*.tar.gz"]
    }
]


def resolver_guia_html() -> Optional[pathlib.Path]:
    """Busca y retorna la ruta del archivo HTML de la guía si existe."""
    for cand in GUIDE_HTML_CANDIDATES:
        try:
            if cand.is_file():
                return cand.resolve()
        except OSError:
            continue
    return None


def preparar_directorio_servido(ruta_html: pathlib.Path) -> Tuple[str, str]:
    """Copia el HTML de la guía a un directorio temporal propio y devuelve
    (directorio, nombre_archivo).

    http.server.SimpleHTTPRequestHandler sirve TODO el directorio que se le
    indique. Si se apuntara directamente al directorio real de la guía
    (p. ej. /workspace cuando guia.html vive en /workspace/guia.html) se
    expondría también loot/ y evidence/ de cualquier engagement del
    operador. Aislar una copia de solo el archivo en un directorio vacío
    evita esa fuga sin importar en qué candidato se haya resuelto la guía.
    """
    directorio_aislado = tempfile.mkdtemp(prefix="seclab-guide-")
    nombre_archivo = "guia.html"
    shutil.copy2(ruta_html, pathlib.Path(directorio_aislado) / nombre_archivo)
    return directorio_aislado, nombre_archivo


def construir_servidor(directorio: str, nombre_archivo: str, puerto: int) -> Tuple[Optional[socketserver.TCPServer], int]:
    """Construye el TCPServer vinculado solo a loopback, probando puertos
    sucesivos si el solicitado está ocupado. Devuelve (httpd, puerto_usado);
    httpd es None si no se pudo vincular ningún puerto."""

    class CustomHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, directory=directorio, **kwargs)

        def do_GET(self) -> None:
            if self.path in ("/", "/index.html", "/guia.html", "/guia"):
                self.path = f"/{nombre_archivo}"
            return super().do_GET()

        def log_message(self, format: str, *args: Any) -> None:
            # Silenciar logs verbosos en la terminal
            sys.stdout.write(f"{C_GRAY}[HTTP] {args[0]} - {args[1]}{C_RESET}\n")

    puerto_actual = puerto
    max_intentos = 10
    for _ in range(max_intentos):
        try:
            # Solo loopback del propio contenedor: nunca exponer este
            # servidor en la red (Tailscale incluida). plan.md sección 2,
            # exposición cero (ver docs/backlog-mejoras.md, acción A2).
            httpd = socketserver.TCPServer(("127.0.0.1", puerto_actual), CustomHandler)
            return httpd, puerto_actual
        except OSError:
            puerto_actual += 1
    return None, puerto_actual


def iniciar_servidor_web(puerto: int = 8888) -> int:
    """Lanza un servidor HTTP local, solo en loopback, sirviendo únicamente
    el archivo HTML de la guía (nunca el directorio que lo contiene)."""
    ruta_html = resolver_guia_html()
    if not ruta_html:
        sys.stderr.write(
            f"{C_RED}Error: no se encontró el archivo guia.html ni guia-laboratorio.html en las rutas estándar.{C_RESET}\n"
        )
        return 1

    directorio_aislado, nombre_archivo = preparar_directorio_servido(ruta_html)
    try:
        httpd, puerto_actual = construir_servidor(directorio_aislado, nombre_archivo, puerto)
        if not httpd:
            sys.stderr.write(f"{C_RED}Error: no se pudo abrir ningún puerto entre {puerto} y {puerto_actual}.{C_RESET}\n")
            return 1

        sys.stdout.write(f"\n{C_BOLD}{C_GREEN}=== Servidor de Ayuda Interactivo de SecLab-SBF Iniciado ==={C_RESET}\n")
        sys.stdout.write(f"{C_CYAN}Archivo servido:{C_RESET} {ruta_html} (copia aislada de solo lectura)\n")
        sys.stdout.write(f"{C_BOLD}{C_YELLOW}Acceso:{C_RESET} http://127.0.0.1:{puerto_actual}/ (solo loopback de este contenedor)\n")
        sys.stdout.write(f"{C_GRAY}Para verla desde tu navegador, abre un túnel, p. ej.: ssh -L {puerto_actual}:127.0.0.1:{puerto_actual} ...{C_RESET}\n")
        sys.stdout.write(f"{C_GRAY}Presiona Ctrl+C para detener el servidor.{C_RESET}\n\n")

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            sys.stdout.write(f"\n{C_YELLOW}Servidor web detenido por el usuario.{C_RESET}\n")
        finally:
            httpd.server_close()
        return 0
    finally:
        shutil.rmtree(directorio_aislado, ignore_errors=True)


def imprimir_portada() -> None:
    """Imprime el banner principal y opciones tácticas."""
    banner = f"""{C_CYAN}
  ╔═══════════════════════════════════════════════════════════════════╗
  ║    🛡️  SECLAB-SBF  |  CENTRO DE ASISTENCIA Y GUÍA DEL OPERADOR    ║
  ║      98 Herramientas · 10 Agent Skills · 8 Fases Metodológicas    ║
  ╚═══════════════════════════════════════════════════════════════════╝{C_RESET}
"""
    sys.stdout.write(banner)
    sys.stdout.write(f"{C_BOLD}¿Qué deseas hacer hoy?{C_RESET}\n\n")
    sys.stdout.write(f"  {C_BOLD}{C_GREEN}1. Auditoría Web / API Profesional (Engagement completo){C_RESET}\n")
    sys.stdout.write(f"     Flujo estandarizado: new -> scope -> recon -> next -> skills -> report -> close\n\n")
    sys.stdout.write(f"  {C_BOLD}{C_BLUE}2. Reto CTF o Máquina de Laboratorio (HackTheBox / TryHackMe){C_RESET}\n")
    sys.stdout.write(f"     Conexión VPN bajo demanda -> nmp escaneo 2 fases -> logging -> post-explotación\n\n")
    sys.stdout.write(f"  {C_BOLD}{C_MAGENTA}3. Orquestación con Modelos de Lenguaje (Claude, GPT, DeepSeek){C_RESET}\n")
    sys.stdout.write(f"     Extracción de contexto determinista (pt-context) y generador de prompts (pt-next --prompt)\n\n")
    sys.stdout.write(f"  {C_BOLD}{C_YELLOW}4. Pivoting, Proxies y Redes Seguras (SOCKS5 / tun0){C_RESET}\n")
    sys.stdout.write(f"     pt-socks, pt-forward y pt-web con Route Guard perimetral hacia tun0\n\n")
    sys.stdout.write(f"  {C_BOLD}{C_CYAN}5. Abrir la Guía Interactiva en el Navegador Web{C_RESET}\n")
    sys.stdout.write(f"     Ejecuta: {C_BOLD}pt-guide --web{C_RESET} (o abre el archivo {C_BOLD}/workspace/guia.html{C_RESET})\n\n")
    sys.stdout.write(f"{C_GRAY}-----------------------------------------------------------------------{C_RESET}\n")
    sys.stdout.write(f"Usa {C_CYAN}pt-guide -h{C_RESET} para ver opciones avanzadas, o {C_CYAN}pt-guide --wizard <nombre> <target>{C_RESET} para generar tu plan.\n")


def imprimir_plan_wizard(nombre: str, target: str) -> None:
    """Genera y muestra en terminal el plan táctico paso a paso para un target dado."""
    sys.stdout.write(f"\n{C_BOLD}{C_GREEN}Plan Táctico Generado para Engagement: {nombre} ({target}){C_RESET}\n")
    sys.stdout.write(f"{C_GRAY}═══════════════════════════════════════════════════════════════════════{C_RESET}\n\n")

    pasos = [
        ("1. Inicializar Engagement y Scope Guard",
         f"pt-eng new {nombre} {target}\ncd /workspace/engagements/{nombre}\npt-scope check target.yaml https://{target}"),
        ("2. Reconocimiento Automatizado con Scope Guard",
         f"pt-recon {nombre}"),
        ("3. Consultar Asesor Táctico y Generar Prompt para LLM",
         f"pt-next --prompt"),
        ("4. Fuzzing de Parámetros Ocultos con x8",
         f"pt-fuzz-params https://{target}/api"),
        ("5. Probar Inyecciones / SSRF con Validación OOB",
         f"pt-callback listen 9001  # Iniciar receptor OOB en segundo panel tmux"),
        ("6. Documentar Hallazgo con Rigor Evidence-First",
         f"pt-finding new idor-usuarios\npt-finding lint"),
        ("7. Evaluar Cobertura Metodológica en 8 Disciplinas",
         f"pt-checklist --markdown"),
        ("8. Compilar Reporte y Cierre Seguro",
         f"pt-report compile\npt-eng close\npt-eng pack")
    ]

    for titulo, comando in pasos:
        sys.stdout.write(f"{C_BOLD}{C_CYAN}▶ {titulo}{C_RESET}\n")
        lineas = comando.strip().split("\n")
        for l in lineas:
            sys.stdout.write(f"  {C_BOLD}{C_YELLOW}$ {l}{C_RESET}\n")
        sys.stdout.write("\n")


def imprimir_disciplina(disc_id: int) -> None:
    """Muestra detalles y comandos para una disciplina específica."""
    disc = next((d for d in DISCIPLINAS if d["id"] == disc_id), None)
    if not disc:
        sys.stderr.write(f"{C_RED}Error: disciplina no válida ({disc_id}). Usa un número del 1 al 8.{C_RESET}\n")
        return

    sys.stdout.write(f"\n{C_BOLD}{C_MAGENTA}=== Disciplina {disc['id']}: {disc['name']} ==={C_RESET}\n")
    sys.stdout.write(f"{C_BOLD}Descripción:{C_RESET} {disc['desc']}\n")
    sys.stdout.write(f"{C_BOLD}Comando Recomendado:{C_RESET} {C_GREEN}{disc['cmd']}{C_RESET}\n")
    sys.stdout.write(f"{C_BOLD}Herramientas Clave:{C_RESET} {', '.join(disc['tools'])}\n")
    sys.stdout.write(f"{C_BOLD}Artefactos Esperados:{C_RESET} {', '.join(disc['artifacts'])}\n\n")


def emitir_json() -> None:
    """Emite la estructura de la guía en formato JSON."""
    ruta_html = resolver_guia_html()
    data = {
        "framework": "seclab-sbf",
        "guide_html_path": str(ruta_html) if ruta_html else None,
        "disciplines": DISCIPLINAS,
        "quick_actions": {
            "engagement": "pt-eng new <nombre> [target]",
            "next_step": "pt-next --prompt",
            "coverage_checklist": "pt-checklist",
            "evidence_finding": "pt-finding new <slug>",
            "report_compiler": "pt-report compile",
            "recon_pipeline": "pt-recon <engagement>",
            "skills_catalog": "pt-skills",
            "cheatsheet": "pt-cheat",
            "vpn_tryhackme": "vpntry",
            "vpn_hackthebox": "vpnhtb",
            "socks_proxy": "pt-socks 1080"
        }
    }
    sys.stdout.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="pt-guide",
        description="Centro de Ayuda, Guía del Operador y Asistente Táctico de SecLab-SBF."
    )
    parser.add_argument(
        "-w", "--web", "--serve",
        action="store_true",
        help="Iniciar servidor HTTP local para abrir la guía interactiva en el navegador."
    )
    parser.add_argument(
        "-p", "--port",
        type=int,
        default=8888,
        help="Puerto para el servidor HTTP embebido (default: 8888)."
    )
    parser.add_argument(
        "-i", "--wizard",
        nargs="*",
        metavar=("NOMBRE", "TARGET"),
        help="Generar secuencia táctica para un proyecto (ej: pt-guide --wizard acme-corp acme.com)."
    )
    parser.add_argument(
        "-d", "--discipline",
        type=int,
        choices=range(1, 9),
        metavar="1-8",
        help="Ver detalles tácticos de una disciplina metodológica específica (1 al 8)."
    )
    parser.add_argument(
        "-j", "--json",
        action="store_true",
        help="Salida estructurada en JSON para integraciones con agentes y herramientas."
    )
    parser.add_argument(
        "--path",
        action="store_true",
        help="Imprimir la ruta absoluta del archivo HTML de la guía."
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.path:
        ruta = resolver_guia_html()
        if ruta:
            sys.stdout.write(str(ruta) + "\n")
            return 0
        sys.stderr.write("No se encontró el archivo HTML de la guía.\n")
        return 1

    if args.json:
        emitir_json()
        return 0

    if args.web:
        return iniciar_servidor_web(args.port)

    if args.discipline:
        imprimir_disciplina(args.discipline)
        return 0

    if args.wizard is not None:
        nombre = args.wizard[0] if len(args.wizard) > 0 else "engagement-audit"
        target = args.wizard[1] if len(args.wizard) > 1 else "target.com"
        imprimir_plan_wizard(nombre, target)
        return 0

    # Por defecto mostrar portada interactiva
    imprimir_portada()
    return 0


if __name__ == "__main__":
    sys.exit(main())
