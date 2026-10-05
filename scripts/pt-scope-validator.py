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

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from seclab_scope import (ScopeError, normalize_target, is_ip, domain_matches,
                          parse_simple_yaml_lists, load_target_yaml, load_scope_txt, check_scope)


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

    try:
        data = load_target_yaml(config_file) if config_file.suffix in (".yaml", ".yml") else load_scope_txt(config_file)
    except (ScopeError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2

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
