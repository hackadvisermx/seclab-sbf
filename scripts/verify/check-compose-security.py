#!/usr/bin/env python3
"""Auditor de seguridad para configuraciones de Docker Compose de SecLab.

Analiza la configuracion resuelta por `docker compose config --format json`
y valida las restricciones de seguridad innegociables del proyecto:
  1. Prohibido `privileged: true` (anulacion de aislamiento).
  2. Prohibido `network_mode: host` (elimina el aislamiento de red).
  3. Prohibidas capacidades peligrosas en `cap_add` (SYS_ADMIN, SYS_PTRACE, etc.).
  4. Prohibido montar el socket de Docker (/var/run/docker.sock).
  5. Prohibido montar sistemas de ficheros raiz o sensibles del host (/, /etc, /root).
  6. Prohibido exponer puertos en 0.0.0.0 (solo loopback 127.0.0.1 permitido).
  7. Obligatorio `cap_drop: ALL` para aplicar minimo privilegio.
  8. Obligatorio `no-new-privileges:true` en security_opt.
"""

import argparse
import json
import sys

DANGEROUS_CAPS = {
    "ALL",
    "SYS_ADMIN",
    "SYS_PTRACE",
    "SYS_MODULE",
    "DAC_READ_SEARCH",
    "MAC_ADMIN",
    "MAC_OVERRIDE",
    "SYS_RAWIO",
}

SAFE_LOCAL_BINDS = {"127.0.0.1", "::1", "localhost"}

SENSITIVE_HOST_MOUNTS = {"/", "/etc", "/root", "/proc", "/sys", "/var/run/docker.sock"}


def analyze_compose(data: dict, name: str = "compose") -> list[str]:
    issues = []
    services = data.get("services") or {}

    if not services:
        issues.append(f"{name}: no se encontraron servicios definidos")
        return issues

    for svc_name, svc in services.items():
        # 1. Privileged check
        if svc.get("privileged") is True:
            issues.append(f"{name}/{svc_name}: usa 'privileged: true', vulnerando el sandbox")

        # 2. Network mode check
        net_mode = svc.get("network_mode")
        if net_mode == "host":
            issues.append(f"{name}/{svc_name}: usa 'network_mode: host', eliminando aislamiento de red")

        # 3. Dangerous capabilities
        cap_add = {str(c).upper() for c in (svc.get("cap_add") or [])}
        dangerous_found = cap_add & DANGEROUS_CAPS
        if dangerous_found:
            issues.append(
                f"{name}/{svc_name}: anade capacidades peligrosas ({', '.join(sorted(dangerous_found))})"
            )

        # 4. Cap drop ALL
        cap_drop = {str(c).upper() for c in (svc.get("cap_drop") or [])}
        if "ALL" not in cap_drop:
            issues.append(f"{name}/{svc_name}: no incluye 'cap_drop: ALL' para minimo privilegio")

        # 5. Security opts (no-new-privileges)
        sec_opts = svc.get("security_opt") or []
        has_no_new_privs = any("no-new-privileges" in str(opt).lower() for opt in sec_opts)
        if not has_no_new_privs:
            issues.append(f"{name}/{svc_name}: falta 'security_opt: [no-new-privileges:true]'")

        # 6. Port bindings (Zero Ingress public)
        ports = svc.get("ports") or []
        for port in ports:
            if isinstance(port, dict):
                host_ip = port.get("host_ip") or "0.0.0.0"
                published = port.get("published")
            else:
                # String format "IP:hostPort:containerPort" or "hostPort:containerPort"
                port_str = str(port)
                parts = port_str.split(":")
                if len(parts) >= 3:
                    host_ip = parts[0]
                    published = parts[1]
                elif len(parts) == 2:
                    host_ip = "0.0.0.0"
                    published = parts[0]
                else:
                    host_ip = "0.0.0.0"
                    published = port_str

            if host_ip not in SAFE_LOCAL_BINDS:
                issues.append(
                    f"{name}/{svc_name}: puerto {published} escucha en {host_ip} (debe ser 127.0.0.1 o no publicar puertos)"
                )

        # 7. Volume mounts
        volumes = svc.get("volumes") or []
        for vol in volumes:
            source = vol.get("source") if isinstance(vol, dict) else str(vol).split(":")[0]
            if not source:
                continue
            if "docker.sock" in source:
                issues.append(
                    f"{name}/{svc_name}: monta el socket de Docker ({source}), equivalente a root en host"
                )
            if source in SENSITIVE_HOST_MOUNTS:
                issues.append(
                    f"{name}/{svc_name}: monta ruta sensible del host ({source})"
                )

    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Auditar seguridad de configuracion Docker Compose")
    parser.add_argument("--name", default="compose", help="Nombre descriptivo de la configuracion")
    args = parser.parse_args()

    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        print(f"compose_security_check=fail error='JSON invalido: {exc}'", file=sys.stderr)
        return 1

    issues = analyze_compose(data, name=args.name)
    if issues:
        print(f"compose_security_check=fail nombre={args.name} problemas={len(issues)}", file=sys.stderr)
        for issue in issues:
            print(f"  → {issue}", file=sys.stderr)
        return 1

    print(f"compose_security_check=ok nombre={args.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
