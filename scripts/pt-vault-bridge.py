#!/usr/bin/env python3
"""SecLab Vault Bridge CLI: Inyector de credenciales y puente táctico para herramientas del laboratorio.

Permite que herramientas como shodan, findomain, nuclei, x8 y scripts pt-* consuman
las API keys almacenadas en el Vault cifrado de SecLab en memoria (vía variables de entorno)
sin escribir credenciales en archivos de disco ni en el historial de comandos.
"""

import argparse
import os
import pathlib
import subprocess
import sys

# Agregar backend al sys.path para acceder a los módulos de seguridad y base de datos
SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
BACKEND_DIR = REPO_ROOT / "dashboard" / "backend"
CONTAINER_BACKEND = pathlib.Path("/usr/local/share/seclab/dashboard/backend")

for candidate in (BACKEND_DIR, CONTAINER_BACKEND):
    if candidate.exists() and str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

try:
    from app.services.vault_service import vault_service
except ImportError:
    # Si corre dentro del venv o en contenedor
    venv_site = REPO_ROOT / "dashboard" / ".venv" / "lib"
    for p in venv_site.glob("python*/site-packages"):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    from app.services.vault_service import vault_service


ENV_MAPPINGS = {
    "shodan": ["SHODAN_API_KEY", "SHODAN_KEY"],
    "censys": ["CENSYS_API_KEY"],
    "virustotal": ["VT_API_KEY", "VIRUSTOTAL_API_KEY"],
    "chaos": ["CHAOS_KEY", "PDCP_API_KEY"],
    "openai": ["OPENAI_API_KEY"],
    "anthropic": ["ANTHROPIC_API_KEY"],
    "gemini": ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
    "hackthebox": ["HTB_API_TOKEN", "HACKTHEBOX_API_KEY"],
    "tryhackme": ["THM_API_KEY", "TRYHACKME_API_KEY"],
}


def cmd_list(args):
    """Lista las claves almacenadas y su estado."""
    keys = vault_service.list_keys()
    if not keys:
        print("No hay claves registradas en el SecLab Vault.")
        return 0

    print(f"{'PROVEEDOR':<15} {'TIPO':<10} {'ESTADO':<12} {'CLAVE ENMASCARADA':<20} {'ETIQUETA'}")
    print("-" * 75)
    for k in keys:
        print(f"{k.provider:<15} {k.service_type:<10} {k.status.upper():<12} {k.masked_key:<20} {k.label}")
    return 0


def cmd_get(args):
    """Obtiene una clave descifrada (para scripts autorizados)."""
    raw_key = vault_service.get_raw_key(args.provider)
    if not raw_key:
        sys.stderr.write(f"Error: Proveedor '{args.provider}' no encontrado o inactivo.\n")
        return 1
    sys.stdout.write(raw_key + "\n")
    return 0


def cmd_run(args):
    """Ejecuta un comando inyectando las credenciales del Vault en su entorno."""
    if not args.command:
        sys.stderr.write("Uso: pt-vault run <comando> [argumentos...]\n")
        return 1

    keys = vault_service.list_keys()
    env = os.environ.copy()

    injected = []
    for k in keys:
        if not k.is_active:
            continue
        raw_key = vault_service.get_raw_key(k.provider)
        if raw_key:
            env_vars = ENV_MAPPINGS.get(k.provider.lower(), [f"{k.provider.upper()}_API_KEY"])
            for var_name in env_vars:
                env[var_name] = raw_key
                injected.append(var_name)

    # Ejecutar subproceso heredando stdin/stdout/stderr
    try:
        proc = subprocess.run(args.command, env=env)
        return proc.returncode
    except FileNotFoundError:
        sys.stderr.write(f"Error: Comando '{args.command[0]}' no encontrado en PATH.\n")
        return 127
    except Exception as e:
        sys.stderr.write(f"Error al ejecutar comando: {str(e)}\n")
        return 1


def main():
    parser = argparse.ArgumentParser(
        description="SecLab Vault Bridge: Inyector seguro de credenciales para herramientas del laboratorio."
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # list
    p_list = subparsers.add_parser("list", help="Lista las claves configuradas con valores enmascarados")
    p_list.set_defaults(func=cmd_list)

    # get
    p_get = subparsers.add_parser("get", help="Imprime la clave descifrada de un proveedor específico")
    p_get.add_argument("provider", help="Nombre del proveedor (ej: shodan, openai)")
    p_get.set_defaults(func=cmd_get)

    # run
    p_run = subparsers.add_parser("run", help="Ejecuta un comando con todas las API keys inyectadas en memoria")
    p_run.add_argument("command", nargs=argparse.REMAINDER, help="Comando a ejecutar con sus argumentos")
    p_run.set_defaults(func=cmd_run)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
