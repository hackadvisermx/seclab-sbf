#!/usr/bin/env python3
"""Validador determinista de alcance (Scope Validator) para SecLab-SBF.

Analiza objetivos (dominios, subdominios, IPs, CIDRs, URLs) contra las reglas
de engagement definidas en target.yaml o scope.txt, previniendo acciones fuera
de alcance o contra exclusiones explicitas.

Sin dependencias externas obligatorias (soporta PyYAML si esta disponible,
con fallback regex/parser integrado y modulo ipaddress de la biblioteca estandar).
"""

import ipaddress
import json
import os
import pathlib
import re
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

# Expresiones regulares para normalizacion y extraccion
URL_HOST_RE = re.compile(r"^(?:https?://)?([^/:]+)(?::\d+)?(?:/.*)?$", re.IGNORECASE)
IPV4_RE = re.compile(r"^(\d{1,3}\.){3}\d{1,3}$")


def normalize_target(raw_target: str) -> str:
    """Extrae el hostname o IP limpia de una URL, host:puerto o ruta."""
    cleaned = raw_target.strip()
    match = URL_HOST_RE.match(cleaned)
    if match:
        return match.group(1).lower()
    return cleaned.split(":")[0].split("/")[0].lower()


def is_ip(target: str) -> bool:
    """Verifica si el objetivo es una direccion IP valida."""
    try:
        ipaddress.ip_address(target)
        return True
    except ValueError:
        return False


def parse_simple_yaml_lists(content: str) -> Dict[str, Any]:
    """Parser liviano de respaldo para target.yaml sin dependencias externas."""
    data: Dict[str, Any] = {
        "scope": {
            "in_scope": {"domains": [], "ips": [], "cidrs": [], "endpoints": []},
            "out_of_scope": {"domains": [], "ips": [], "cidrs": [], "notes": []},
        },
        "operational_limits": {},
        "engagement": {},
    }

    current_section = None
    current_sub = None
    current_list = None

    for line in content.splitlines():
        line_str = line.strip()
        if not line_str or line_str.startswith("#"):
            continue

        # Deteccion de secciones principales
        if line.startswith("engagement:"):
            current_section = "engagement"
            continue
        elif line.startswith("scope:"):
            current_section = "scope"
            continue
        elif line.startswith("operational_limits:"):
            current_section = "operational_limits"
            continue

        if current_section == "scope":
            if line.startswith("  in_scope:"):
                current_sub = "in_scope"
                current_list = None
                continue
            elif line.startswith("  out_of_scope:"):
                current_sub = "out_of_scope"
                current_list = None
                continue

            if current_sub in ("in_scope", "out_of_scope"):
                list_match = re.match(r"^\s{4}([a-z_]+):(?:\s*\[(.*)\])?", line)
                if list_match:
                    key = list_match.group(1)
                    inline_items = list_match.group(2)
                    current_list = key
                    if inline_items is not None:
                        items = [i.strip(" '\"") for i in inline_items.split(",") if i.strip(" '\"")]
                        data["scope"][current_sub][key] = items
                    elif key not in data["scope"][current_sub]:
                        data["scope"][current_sub][key] = []
                    continue

                item_match = re.match(r"^\s{6}-\s*[\"']?([^\"']+)[\"']?", line)
                if item_match and current_list:
                    item_val = item_match.group(1).strip()
                    if current_list not in data["scope"][current_sub]:
                        data["scope"][current_sub][current_list] = []
                    data["scope"][current_sub][current_list].append(item_val)

        elif current_section in ("engagement", "operational_limits"):
            kv_match = re.match(r"^\s{2}([a-z_]+):\s*[\"']?([^\"']+)[\"']?", line)
            if kv_match:
                k, v = kv_match.group(1), kv_match.group(2).strip()
                data[current_section][k] = v

    return data


def load_target_yaml(yaml_path: pathlib.Path) -> Dict[str, Any]:
    """Carga y parsea target.yaml usando PyYAML si existe o fallback integrado."""
    content = yaml_path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        loaded = yaml.safe_load(content)
        if isinstance(loaded, dict):
            return loaded
    except Exception:
        pass
    return parse_simple_yaml_lists(content)


def load_scope_txt(txt_path: pathlib.Path) -> Dict[str, Any]:
    """Parsea el formato tradicional scope.txt de seclab-sbf."""
    content = txt_path.read_text(encoding="utf-8")
    in_scope: List[str] = []
    out_of_scope: List[str] = []

    current_section = None
    for line in content.splitlines():
        line_clean = line.strip()
        if line_clean.startswith("## Activos y Objetivos en Alcance"):
            current_section = "in"
            continue
        elif line_clean.startswith("## Fuera de Alcance"):
            current_section = "out"
            continue
        elif line_clean.startswith("## "):
            current_section = None
            continue

        if line_clean.startswith("- "):
            item = line_clean[2:].strip().split()[0].strip("[]()")
            if current_section == "in" and item:
                in_scope.append(item)
            elif current_section == "out" and item:
                out_of_scope.append(item)

    domains_in, ips_in, cidrs_in = [], [], []
    for item in in_scope:
        if "/" in item and not item.startswith("http"):
            cidrs_in.append(item)
        elif is_ip(item):
            ips_in.append(item)
        else:
            domains_in.append(normalize_target(item))

    domains_out, ips_out, cidrs_out = [], [], []
    for item in out_of_scope:
        if "/" in item and not item.startswith("http"):
            cidrs_out.append(item)
        elif is_ip(item):
            ips_out.append(item)
        else:
            domains_out.append(normalize_target(item))

    return {
        "scope": {
            "in_scope": {"domains": domains_in, "ips": ips_in, "cidrs": cidrs_in},
            "out_of_scope": {"domains": domains_out, "ips": ips_out, "cidrs": cidrs_out},
        }
    }


def domain_matches(target: str, pattern: str) -> bool:
    """Verifica si target coincide con pattern (exacto o wildcard *.dominio)."""
    target = target.lower()
    pattern = pattern.lower().strip()
    if pattern.startswith("*."):
        suffix = pattern[2:]
        return target == suffix or target.endswith("." + suffix)
    return target == pattern or target.endswith("." + pattern)


def check_scope(target: str, scope_data: Dict[str, Any]) -> Tuple[str, str]:
    """Evalua si target es OUT_OF_SCOPE, IN_SCOPE o UNKNOWN.

    Retorna: (veredicto, regla_coincidente)
    """
    clean_target = normalize_target(target)
    scope = scope_data.get("scope", {})
    in_scope = scope.get("in_scope", {})
    out_of_scope = scope.get("out_of_scope", {})

    target_is_ip = is_ip(clean_target)
    target_addr = ipaddress.ip_address(clean_target) if target_is_ip else None

    # 1. EVALUAR PRIMERO EXCLUSIONES (OUT_OF_SCOPE)
    if target_is_ip and target_addr:
        # IPs explicitas excluidas
        for o_ip in out_of_scope.get("ips", []):
            try:
                if target_addr == ipaddress.ip_address(o_ip.strip()):
                    return ("OUT_OF_SCOPE", f"IP excluida: {o_ip}")
            except ValueError:
                pass
        # CIDRs excluidos
        for o_cidr in out_of_scope.get("cidrs", []):
            try:
                if target_addr in ipaddress.ip_network(o_cidr.strip(), strict=False):
                    return ("OUT_OF_SCOPE", f"CIDR excluido: {o_cidr}")
            except ValueError:
                pass
    else:
        # Dominios excluidos
        for o_dom in out_of_scope.get("domains", []):
            if domain_matches(clean_target, o_dom):
                return ("OUT_OF_SCOPE", f"Dominio excluido: {o_dom}")

    # 2. EVALUAR COINCIDENCIA EN ALCANCE (IN_SCOPE)
    if target_is_ip and target_addr:
        for i_ip in in_scope.get("ips", []):
            try:
                if target_addr == ipaddress.ip_address(i_ip.strip()):
                    return ("IN_SCOPE", f"IP autorizada: {i_ip}")
            except ValueError:
                pass
        for i_cidr in in_scope.get("cidrs", []):
            try:
                if target_addr in ipaddress.ip_network(i_cidr.strip(), strict=False):
                    return ("IN_SCOPE", f"CIDR autorizado: {i_cidr}")
            except ValueError:
                pass
    else:
        for i_dom in in_scope.get("domains", []):
            if domain_matches(clean_target, i_dom):
                return ("IN_SCOPE", f"Dominio autorizado: {i_dom}")

    return ("UNKNOWN", "No listado explicitamente en el alcance ni en exclusiones")


def main() -> int:
    if len(sys.argv) < 3:
        print("Uso: pt-scope-validator.py <check|show> <ruta_archivo_o_dir> [target]", file=sys.stderr)
        return 2

    action = sys.argv[1]
    path_arg = pathlib.Path(sys.argv[2])

    # Resolver fichero de configuracion
    config_file: Optional[pathlib.Path] = None
    if path_arg.is_dir():
        if (path_arg / "target.yaml").is_file():
            config_file = path_arg / "target.yaml"
        elif (path_arg / "scope.txt").is_file():
            config_file = path_arg / "scope.txt"
    elif path_arg.is_file():
        config_file = path_arg

    if not config_file or not config_file.is_file():
        print(f"Error: No se encontro target.yaml ni scope.txt en {path_arg}", file=sys.stderr)
        return 2

    # Cargar datos segun extension
    if config_file.suffix in (".yaml", ".yml"):
        data = load_target_yaml(config_file)
    else:
        data = load_scope_txt(config_file)

    if action == "check":
        if len(sys.argv) < 4:
            print("Error: Se requiere especificar el objetivo a validar.", file=sys.stderr)
            return 2
        target = sys.argv[3]
        verdict, reason = check_scope(target, data)
        clean = normalize_target(target)

        # Retornar formato estructurado para shells
        if verdict == "OUT_OF_SCOPE":
            print(f"[!] ALERTA CRITICA: '{clean}' esta FUERA DE ALCANCE ({reason})")
            return 1
        elif verdict == "IN_SCOPE":
            print(f"[+] ALCANCE VALIDO: '{clean}' esta DENTRO DE ALCANCE ({reason})")
            return 0
        else:
            print(f"[?] NO IDENTIFICADO: '{clean}' no figura en el alcance ({reason})")
            return 3

    elif action == "show":
        scope = data.get("scope", {})
        in_s = scope.get("in_scope", {})
        out_s = scope.get("out_of_scope", {})
        print("================================================================================")
        print(f"=== REGLAS DE ALCANCE: {config_file.parent.name} ({config_file.name})")
        print("================================================================================")
        print("ACTIVOS AUTORIZADOS (IN-SCOPE):")
        for d in in_s.get("domains", []):
            print(f"  [dominio] {d}")
        for ip in in_s.get("ips", []):
            print(f"  [ip]      {ip}")
        for c in in_s.get("cidrs", []):
            print(f"  [cidr]    {c}")
        if not any(in_s.values()):
            print("  (Sin objetivos definidos)")

        print("\nEXCLUSIONES ESTRICTAS (OUT-OF-SCOPE):")
        for d in out_s.get("domains", []):
            print(f"  [dominio] {d}")
        for ip in out_s.get("ips", []):
            print(f"  [ip]      {ip}")
        for c in out_s.get("cidrs", []):
            print(f"  [cidr]    {c}")
        for n in out_s.get("notes", []):
            print(f"  [nota]    {n}")
        if not any(out_s.values()):
            print("  (Sin exclusiones explícitas)")
        print("================================================================================")
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
