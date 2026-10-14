#!/usr/bin/env python3
"""Gestor, Schema y Validador de Playbooks Deterministas para SecLab-SBF (V3-04).

Define el esquema canónico para procedimientos reproducibles de auditoría (Playbooks),
valida la estructura de pasos, parámetros y condiciones de parada, y comprueba que
los permisos requeridos (pasivos/activos) estén autorizados contra el contrato de
alcance (target.yaml) antes de cualquier ejecución.

Sin dependencias externas obligatorias (Python 3 stdlib + yaml si disponible).
"""

import ipaddress
import json
import os
import pathlib
import re
import shlex
import subprocess
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    import yaml
except ImportError:
    yaml = None

VALID_INTERACTION_TYPES = {"passive", "active_low", "active_high"}
STEP_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_.-]{3,64}$")


class PlaybookValidationError(ValueError):
    """Excepción cuando un playbook no cumple con el esquema o restricciones de seguridad."""
    pass


def _parse_yaml_basic(content: str) -> Dict[str, Any]:
    """Parser básico de YAML para playbooks cuando PyYAML no está disponible."""
    result: Dict[str, Any] = {}
    current_step: Optional[Dict[str, Any]] = None
    in_steps = False
    current_list_key: Optional[str] = None

    for raw_line in content.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        indent = len(raw_line) - len(raw_line.lstrip())

        # Top-level keys (indent == 0)
        if indent == 0:
            current_list_key = None
            current_step = None
            if stripped == "steps:":
                in_steps = True
                result["steps"] = []
                continue
            if ":" in stripped:
                k, v = stripped.split(":", 1)
                k = k.strip()
                v = v.strip().strip("\"'")
                result[k] = v
                in_steps = False
                continue

        # Inside steps list
        if in_steps:
            # Step entry starts at indent <= 2
            if indent <= 2 and stripped.startswith("- "):
                current_step = {}
                result["steps"].append(current_step)
                current_list_key = None
                rest = stripped[2:].strip()
                if ":" in rest:
                    k, v = rest.split(":", 1)
                    k = k.strip()
                    v = v.strip().strip("\"'")
                    current_step[k] = int(v) if v.isdigit() else v
                continue

            if current_step is not None:
                # Sub-list item (indent > 2)
                if stripped.startswith("- "):
                    val = stripped[2:].strip().strip("\"'")
                    if current_list_key:
                        current_step.setdefault(current_list_key, []).append(val)
                    continue

                if ":" in stripped:
                    k, v = stripped.split(":", 1)
                    k = k.strip()
                    v = v.strip()
                    if not v:
                        current_list_key = k
                        current_step[k] = []
                    else:
                        current_list_key = None
                        v_clean = v.strip("\"'")
                        current_step[k] = int(v_clean) if v_clean.isdigit() else v_clean

    return result


def load_playbook_file(path: Union[str, pathlib.Path]) -> Dict[str, Any]:
    """Carga y parsea un archivo de playbook YAML o JSON."""
    file_path = pathlib.Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"Archivo de playbook no encontrado: {file_path}")

    content = file_path.read_text(encoding="utf-8")
    if not content.strip():
        raise PlaybookValidationError("El archivo de playbook está vacío.")

    if yaml is not None:
        try:
            data = yaml.safe_load(content)
        except Exception as e:
            raise PlaybookValidationError(f"Error al parsear YAML del playbook: {e}") from e
    else:
        # Intentar formato JSON primero, y fallback a parser YAML básico
        try:
            data = json.loads(content)
        except Exception:
            try:
                data = _parse_yaml_basic(content)
            except Exception as e:
                raise PlaybookValidationError(f"Error al parsear playbook sin PyYAML: {e}") from e

    if not isinstance(data, dict):
        raise PlaybookValidationError("El playbook debe ser un objeto/mapeo estructurado.")

    return data


def validate_playbook_schema(playbook: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Valida que el playbook cumpla con el esquema formal V3-04a.
    
    Devuelve (es_valido, lista_de_errores).
    """
    errors: List[str] = []

    if not isinstance(playbook, dict):
        return False, ["El contenido del playbook debe ser un diccionario."]

    # Campos obligatorios de nivel superior
    for field in ("id", "title", "version", "category", "steps"):
        if field not in playbook or not playbook[field]:
            errors.append(f"Falta el campo obligatorio de nivel superior '{field}'.")

    playbook_id = str(playbook.get("id", ""))
    if playbook_id and not STEP_ID_PATTERN.match(playbook_id):
        errors.append(f"ID de playbook inválido '{playbook_id}'. Debe contener entre 3 y 64 caracteres alfanuméricos.")

    steps = playbook.get("steps")
    if not isinstance(steps, list) or len(steps) == 0:
        errors.append("El playbook debe contener una lista no vacía de 'steps'.")
        return False, errors

    seen_step_ids = set()
    for idx, step in enumerate(steps):
        prefix = f"Paso {idx + 1}"
        if not isinstance(step, dict):
            errors.append(f"{prefix}: Cada paso debe ser un objeto estructurado.")
            continue

        step_id = step.get("id")
        if not step_id or not isinstance(step_id, str):
            errors.append(f"{prefix}: Falta el campo 'id' del paso.")
        elif not STEP_ID_PATTERN.match(step_id):
            errors.append(f"{prefix}: ID de paso '{step_id}' inválido.")
        elif step_id in seen_step_ids:
            errors.append(f"{prefix}: ID de paso duplicado '{step_id}'.")
        else:
            seen_step_ids.add(step_id)

        title = step.get("title")
        if not title or not isinstance(title, str):
            errors.append(f"{prefix}: Falta el 'title' descriptivo del paso.")

        objective = step.get("objective")
        if not objective or not isinstance(objective, str):
            errors.append(f"{prefix}: Falta el 'objective' del paso.")

        interaction = step.get("interaction_type")
        if interaction not in VALID_INTERACTION_TYPES:
            errors.append(
                f"{prefix}: 'interaction_type' debe ser uno de {sorted(list(VALID_INTERACTION_TYPES))}, recibido: '{interaction}'."
            )

        req_perms = step.get("required_permissions")
        if req_perms is not None and not isinstance(req_perms, list):
            errors.append(f"{prefix}: 'required_permissions' debe ser una lista de permisos.")

        cmd = step.get("command_template")
        if not cmd or not isinstance(cmd, str):
            errors.append(f"{prefix}: Falta 'command_template' ejecutable para el paso.")

        timeout = step.get("timeout_seconds", 300)
        if not isinstance(timeout, int) or timeout <= 0 or timeout > 3600:
            errors.append(f"{prefix}: 'timeout_seconds' debe ser un entero positivo entre 1 y 3600.")

        expected_outs = step.get("expected_outputs")
        if expected_outs is not None and not isinstance(expected_outs, list):
            errors.append(f"{prefix}: 'expected_outputs' debe ser una lista de rutas de artefactos esperados.")

    return len(errors) == 0, errors


NON_TARGET_PLACEHOLDERS = {
    "wordlist",
    "wordlists",
    "timeout",
    "timeout_seconds",
    "format",
    "threads",
    "output",
    "rate",
    "delay",
    "user_agent",
    "cookie",
    "header",
    "headers",
    "port",
    "ports",
    "method",
    "methods",
}

TARGET_KEY_HINTS = {
    "target",
    "targets",
    "domain",
    "domains",
    "host",
    "hosts",
    "ip",
    "ips",
    "nameserver",
    "nameservers",
    "endpoint",
    "endpoints",
    "url",
    "urls",
    "fqdn",
    "hostname",
    "vhost",
    "proxy",
    "proxy_host",
    "proxy_url",
    "dest",
    "destination",
}

COMPACT_TARGET_SHORT_FLAGS = {"-x"}

TARGET_FLAGS_WITH_VALUE = {
    "-x", "--proxy", "--proxy-server", "--http-proxy", "--https-proxy",
    "--socks4", "--socks4a", "--socks5", "--socks5-hostname", "--doh-url", "--preproxy",
    "-u", "--url", "--target", "--host", "--domain",
    "-connect", "--connect", "-servername", "--servername",
}

TARGET_FLAG_NAMES = {
    "-x", "--proxy", "--proxy-server", "--http-proxy", "--https-proxy",
    "--socks4", "--socks4a", "--socks5", "--socks5-hostname", "--doh-url", "--preproxy",
    "-u", "--url", "--target", "--host", "--domain",
    "-s", "--server", "-connect", "--connect", "-servername", "--servername",
}

FLAGS_EXPECTING_NON_TARGET_VALUE = {
    "-X", "-m", "--method", "-w", "--wordlist", "-o", "-oN", "-oJ", "-oX",
    "--output", "--script", "--script-args", "-p", "--ports", "-t", "-T",
    "-T3", "-T4", "--timeout", "-timeout", "-mc", "-H", "--header",
    "-d", "--data", "-f", "--format", "-l", "-b", "--cookie",
    "-A", "--user-agent", "-user-agent", "--data-raw", "--data-binary",
}


def _flag_alternation(flags) -> str:
    # Orden descendente por longitud para que prefijos cortos no eclipsen banderas compuestas
    return "|".join(re.escape(f) for f in sorted(flags, key=len, reverse=True))


def is_target_placeholder(placeholder: str, cmd_tpl: str) -> bool:
    """Determina si un placeholder corresponde a un destino de red verificable contra Scope Guard."""
    p_lower = placeholder.lower()
    if p_lower in NON_TARGET_PLACEHOLDERS:
        return False
    if p_lower in TARGET_KEY_HINTS:
        return True
    escaped = re.escape(placeholder)
    ph = r"\{" + escaped + r"\}"
    value_suffix = r"[^\s'\"`;|<>&]*" + ph + r"[^\s'\"`;|<>&]*"
    space_flags = _flag_alternation(TARGET_FLAGS_WITH_VALUE)
    eq_flags = _flag_alternation(TARGET_FLAG_NAMES)
    compact_flags = _flag_alternation(COMPACT_TARGET_SHORT_FLAGS)
    target_patterns = [
        r"://[^\s'\"`;|<>&]*" + ph,
        r"@\{" + escaped + r"\}",
        r"(?<!\S)(?:" + space_flags + r")\s+['\"]?" + value_suffix,
        r"(?<!\S)(?:" + eq_flags + r")=['\"]?" + value_suffix,
        r"(?<!\S)(?:" + compact_flags + r")['\"]?" + value_suffix,
        r"(?<!\S)-[a-zA-Z0-9]*x['\"]?" + value_suffix,
    ]
    if any(re.search(pat, cmd_tpl) for pat in target_patterns):
        return True

    # Comprobar si está tras una bandera explícitamente no-objetivo (ej. -X {verb}, -d '...{name}...')
    non_target_flags = _flag_alternation(FLAGS_EXPECTING_NON_TARGET_VALUE)
    non_target_patterns = [
        r"(?<!\S)(?:" + non_target_flags + r")\s+['\"]?[^\s'\"`;|<>&]*" + ph,
        r"(?<!\S)(?:" + non_target_flags + r")=['\"]?[^\s'\"`;|<>&]*" + ph,
        r"(?<!\S)(?:" + non_target_flags + r")\s+'[^']*" + ph,
        r'(?<!\S)(?:' + non_target_flags + r')\s+"[^"]*' + ph,
        r"(?<!\S)(?:" + non_target_flags + r")='[^']*" + ph,
        r'(?<!\S)(?:' + non_target_flags + r')="[^"]*' + ph,
    ]
    if any(re.search(pat, cmd_tpl) for pat in non_target_patterns):
        return False

    # Por defecto en pasos activos: cualquier placeholder posicional o ambiguo se considera candidato a destino (fail-closed)
    return True


EXCLUDED_FILE_EXTENSIONS = {
    ".txt",
    ".lst",
    ".csv",
    ".json",
    ".yaml",
    ".yml",
    ".sh",
    ".py",
    ".md",
    ".log",
    ".db",
    ".conf",
    ".sql",
    ".html",
    ".xml",
    ".tar",
    ".gz",
    ".zip",
    ".pdf",
    ".png",
    ".jpg",
    ".svg",
    ".lock",
    ".bak",
    ".tmp",
    ".swp",
}


DYNAMIC_SHELL_PATTERN = re.compile(r"(\$[A-Za-z_][A-Za-z0-9_]*|\$\{[^}]+\}|\$\([^)]+\)|`[^`]+`)")


def step_has_unverified_dynamic_targets(cmd_tpl: str) -> bool:
    """Detecta si el comando usa sustituciones shell dinámicas ($VAR, `cmd`, $(cmd)) no verificables."""
    return bool(DYNAMIC_SHELL_PATTERN.search(cmd_tpl))

DNS_QUERY_TYPES = {
    "any", "a", "aaaa", "cname", "mx", "ns", "ptr", "soa", "srv", "txt", "axfr", "ixfr",
}

COMMAND_SUBCOMMANDS = {
    "openssl": {"s_client", "s_server", "x509", "req", "rsa"},
    "ip": {"neighbor", "show", "route", "addr", "link", "rule"},
}


def _extract_literal_targets(cmd_tpl: str) -> List[str]:
    """Extrae de forma exhaustiva todos los destinos literales de red en una plantilla de comando.

    Identifica:
    - URIs con cualquier esquema de red (http://, https://, ftp://, ws://, etc.).
    - Direcciones IPv6 sin corchetes (ej. 2001:db8::bad) y con corchetes/puertos ([2001:db8::bad]:8080).
    - Direcciones IPv4 directas, con puertos o rutas (192.168.1.1:8080, 192.168.1.1/api).
    - Nombres de host/dominio/FQDN con o sin puertos y rutas (evil.com/path, evil.com:8080/path).
    - Hosts de una sola etiqueta (localhost, db, service, etc.) en posición de argumento o asignación.
    - Asignaciones de flags de comandos (--url=ftp://evil.com, -u=evil.com/path).
    - Tokens sospechosos de red para verificación estricta en Scope Guard.
    """
    targets: List[str] = []

    # 1. URIs completas con cualquier esquema (http, https, ftp, ws, etc.)
    for url in re.findall(r"[a-zA-Z][a-zA-Z0-9+.-]*://[^\s'\"`;|<>&]+", cmd_tpl):
        if "{" not in url and "}" not in url:
            if url not in targets:
                targets.append(url)

    # 2. Dividir comando en segmentos por operadores de control y tubería (;, |, &&, ||)
    segments = re.split(r";|&&|\|\||\|", cmd_tpl)
    tokens_to_inspect: List[str] = []

    for seg in segments:
        seg = seg.strip()
        if not seg:
            continue

        try:
            tokens = shlex.split(seg)
        except ValueError:
            tokens = seg.split()

        if not tokens:
            continue

        cmd_bin = tokens[0].lower().strip("'\"")
        args = tokens[1:]

        skip_next = False
        expect_target_next = False
        for tok in args:
            tok_clean = tok.strip("'\"")

            if skip_next:
                skip_next = False
                continue

            if expect_target_next:
                expect_target_next = False
                if not tok_clean.startswith(("-", "@", "+")):
                    tokens_to_inspect.append(tok_clean)
                    continue

            # Redirecciones
            if tok_clean in (">", ">>", "<", "2>&1", "1>&2", ">&"):
                skip_next = True
                continue
            if tok_clean.startswith(("<", ">")):
                continue

            # Banderas con valores asignados via '='
            if tok_clean.startswith(("-", "--")) and "=" in tok_clean:
                flag_name, flag_val = tok_clean.split("=", 1)
                flag_val = flag_val.strip("'\"")
                if flag_name in TARGET_FLAG_NAMES or flag_name.lower() in TARGET_FLAG_NAMES:
                    if flag_val and flag_val not in targets and "{" not in flag_val:
                        tokens_to_inspect.append(flag_val)
                continue

            # Banderas compactas de proxy (-xVALOR) o agrupadas en curl (-sSxVALOR o -sSx VALOR)
            if tok_clean.startswith("-") and not tok_clean.startswith("--"):
                if cmd_bin == "curl" and "x" in tok_clean:
                    m_clustered = re.match(r"^-[a-zA-Z0-9]*x(.+)$", tok_clean)
                    if m_clustered:
                        compact_val = m_clustered.group(1).strip("'\"")
                        if compact_val and compact_val not in targets and "{" not in compact_val:
                            tokens_to_inspect.append(compact_val)
                        continue
                    elif re.match(r"^-[a-zA-Z0-9]*x$", tok_clean):
                        expect_target_next = True
                        continue
                elif tok_clean.startswith("-x") and len(tok_clean) > 2:
                    compact_val = tok_clean[2:].strip("'\"")
                    if compact_val and compact_val not in targets and "{" not in compact_val:
                        tokens_to_inspect.append(compact_val)
                    continue

            # Banderas que esperan un destino de red
            if tok_clean in TARGET_FLAGS_WITH_VALUE:
                expect_target_next = True
                continue

            # Banderas que consumen el siguiente argumento no-objetivo (sensible a mayúsculas)
            if tok_clean in FLAGS_EXPECTING_NON_TARGET_VALUE:
                skip_next = True
                continue

            # Banderas comunes
            if tok_clean.startswith(("-", "@", "+")):
                continue

            # Subcomandos específicos conocidos por herramienta
            if cmd_bin in COMMAND_SUBCOMMANDS and tok_clean.lower() in COMMAND_SUBCOMMANDS[cmd_bin]:
                continue
            if cmd_bin == "dig" and tok_clean.lower() in DNS_QUERY_TYPES:
                continue

            tokens_to_inspect.append(tok_clean)

    for tok in tokens_to_inspect:
        clean = tok.rstrip(",;")
        if not clean or clean in targets or "://" in clean or clean.startswith("{") or clean.endswith("}"):
            continue

        # Excluir rutas de archivos por extensión
        clean_ext = "." + clean.rsplit(".", 1)[-1].lower() if "." in clean else ""
        if clean_ext in EXCLUDED_FILE_EXTENSIONS:
            continue

        # Excluir números puros (ej. puertos o códigos HTTP)
        if clean.isdigit() or re.fullmatch(r"[0-9,]+", clean):
            continue

        # IPv6 entre corchetes: [2001:db8::bad] o [2001:db8::bad]:8080
        if clean.startswith("[") and "]" in clean:
            b_cand = clean[1:clean.index("]")]
            try:
                ipaddress.ip_address(b_cand)
                if b_cand not in targets:
                    targets.append(b_cand)
                continue
            except ValueError:
                pass

        # IP directa (IPv4 o IPv6 sin corchetes como 2001:db8::bad)
        try:
            ipaddress.ip_address(clean)
            if clean not in targets:
                targets.append(clean)
            continue
        except ValueError:
            pass

        # IPv4 con puerto (ej. 192.168.1.1:8080)
        if ":" in clean and clean.count(":") == 1:
            h, _, p = clean.partition(":")
            p_val = p.split("/")[0]
            if p_val.isdigit():
                try:
                    ipaddress.ip_address(h)
                    if h not in targets:
                        targets.append(h)
                    continue
                except ValueError:
                    pass

        # IP con ruta (ej. 192.168.1.1/api o 2001:db8::bad/path)
        if "/" in clean:
            h = clean.split("/")[0]
            try:
                ipaddress.ip_address(h)
                if clean not in targets:
                    targets.append(clean)
                if h not in targets:
                    targets.append(h)
                continue
            except ValueError:
                pass

        # Nombres de host / dominio / FQDN (con o sin puerto, con o sin ruta)
        host = clean.split("/")[0]
        if ":" in host and not host.startswith("["):
            host = host.split(":")[0]
        if host.startswith("[") and "]" in host:
            host = host[1:host.index("]")]

        # Excluir si la parte de host termina con extensión de archivo
        if "." in host and not host.startswith((".", "-")):
            ext = "." + host.rsplit(".", 1)[-1].lower()
            if ext in EXCLUDED_FILE_EXTENSIONS:
                continue

        # Dominio con punto (FQDN)
        if "." in host and not host.startswith((".", "-")):
            if re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+", host):
                if clean not in targets:
                    targets.append(clean)
                if host not in targets:
                    targets.append(host)
                continue

        # Host de una sola etiqueta (RFC 1123: localhost, db, service, test, get, etc.)
        if re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?", host):
            if clean not in targets:
                targets.append(clean)
            if host not in targets:
                targets.append(host)
            continue

        # Posible IPv6 con múltiples colones que falló sintaxis estricta (para que Scope Guard evalúe y bloquee)
        if clean.count(":") >= 2:
            if clean not in targets:
                targets.append(clean)

    return targets


def extract_step_targets(
    step: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None,
    dry_run: bool = True,
) -> Tuple[List[str], Optional[str]]:
    """Extrae de manera exhaustiva todos los destinos que consumirá un paso.

    Inspecciona:
    1. Placeholders en command_template que provienen de parameters (excluyendo flags operacionales).
    2. Parámetros provistos con nombres canónicos de destino (target, domain, endpoint, etc.).
    3. Archivos referenciados por target_selector o inputs destinados como listas de objetivos.
    4. Destinos literales en command_template (URLs, IPs y dominios no mediados por placeholders).

    Retorna una tupla (targets_list, missing_file_error).
    """
    ctx = context or {}
    params = ctx.get("parameters") or {}
    cmd_tpl = step.get("command_template", "")
    target_selector = str(step.get("target_selector") or "").strip()
    inputs = step.get("inputs") or []

    targets: List[str] = []
    missing_file_error: Optional[str] = None

    # 1. Placeholders en la plantilla de comandos
    placeholders = re.findall(r"\{([a-zA-Z0-9_]+)\}", cmd_tpl)
    for p in placeholders:
        if is_target_placeholder(p, cmd_tpl) and p in params and params[p] is not None:
            val = str(params[p]).strip()
            if val:
                parts = [part.strip() for part in re.split(r"[,\s]+", val) if part.strip()]
                for part in parts:
                    if part not in targets:
                        targets.append(part)

    # 2. Claves de parámetros canónicos que puedan contener destinos
    for k, v in params.items():
        if v is not None and k.lower() in TARGET_KEY_HINTS:
            val = str(v).strip()
            if val:
                parts = [part.strip() for part in re.split(r"[,\s]+", val) if part.strip()]
                for part in parts:
                    if part not in targets:
                        targets.append(part)

    # 3. Selectores o insumos basados en archivos (M5: distinguir listas de objetivos vs artefactos)
    file_candidates: List[str] = []
    if target_selector and (
        target_selector.endswith((".txt", ".lst", ".csv"))
        or "/" in target_selector
        or "\\" in target_selector
    ) and target_selector not in ("in_scope_domains", "in_scope_ips", "local_gateway", "domains", "ips", "live_hosts"):
        file_candidates.append(target_selector)

    has_target_placeholders = any(
        p.lower() not in NON_TARGET_PLACEHOLDERS
        for p in placeholders
    )
    is_standard_selector = target_selector in ("in_scope_domains", "in_scope_ips", "domains", "ips", "live_hosts")

    for inp in inputs:
        if isinstance(inp, str):
            inp_clean = inp.strip()
            if (
                inp_clean.endswith((".txt", ".lst", ".csv"))
                and inp_clean not in ("target.yaml", "scope.txt")
                and inp_clean not in file_candidates
            ):
                # Solo se considera fuente de objetivos si el paso no tiene placeholders de destino
                # ni selector canónico, o si el archivo está explícitamente en el comando
                if not has_target_placeholders and not is_standard_selector:
                    file_candidates.append(inp_clean)
                elif inp_clean in cmd_tpl:
                    file_candidates.append(inp_clean)

    # Resolver archivos en engagement_dir
    engagement_dir = ctx.get("engagement_dir")
    if not engagement_dir and ctx.get("target_yaml_path"):
        engagement_dir = str(pathlib.Path(ctx["target_yaml_path"]).parent)

    for f_rel in file_candidates:
        f_path = (pathlib.Path(engagement_dir) / f_rel) if engagement_dir else pathlib.Path(f_rel)
        if f_path.is_file():
            try:
                lines = [
                    line.strip()
                    for line in f_path.read_text(encoding="utf-8").splitlines()
                    if line.strip() and not line.strip().startswith("#")
                ]
                if not lines:
                    missing_file_error = f"El archivo de objetivos '{f_rel}' está vacío."
                for line in lines:
                    if line not in targets:
                        targets.append(line)
            except Exception as e:
                missing_file_error = f"Error al leer archivo de objetivos '{f_rel}': {e}"
        elif not dry_run:
            missing_file_error = f"El archivo de objetivos '{f_rel}' no existe en el proyecto."

    # 4. Destinos literales en command_template mediante extractor canónico unificado
    for lit_target in _extract_literal_targets(cmd_tpl):
        if lit_target not in targets:
            targets.append(lit_target)

    # 5. Si hay parámetros provistos, extraer también destinos literales del comando interpolado
    if params:
        try:
            interp_cmd = interpolate_command(cmd_tpl, params)
            for lit_target in _extract_literal_targets(interp_cmd):
                if lit_target not in targets:
                    targets.append(lit_target)
        except Exception:
            pass

    return targets, missing_file_error


def step_has_declared_target_source(step: Dict[str, Any]) -> bool:
    """Comprueba si un paso declara una fuente explícita para resolver objetivos de alcance."""
    target_selector = str(step.get("target_selector") or "").strip()
    if target_selector:
        return True
    if step.get("inputs"):
        return True
    cmd_tpl = step.get("command_template", "")
    placeholders = re.findall(r"\{([a-zA-Z0-9_]+)\}", cmd_tpl)
    for p in placeholders:
        if p.lower() not in NON_TARGET_PLACEHOLDERS:
            return True
    # Destinos literales en el comando usando el extractor canónico unificado
    if _extract_literal_targets(cmd_tpl):
        return True
    return False


def validate_playbook_against_scope(
    playbook: Dict[str, Any],
    target_yaml_path: Union[str, pathlib.Path],
    parameters: Optional[Dict[str, Any]] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Evalúa los permisos de cada paso del playbook contra la autorización y alcance de target.yaml.
    
    Verifica que las interacciones activas ('active_low', 'active_high') cuenten con
    'allow_active: true', las pasivas con 'allow_passive: true', la ventana de vigencia
    esté activa en el momento evaluado (require_authorization), y los destinos provistos
    en parameters cumplan con Scope Guard (check_scope).
    """
    is_valid, errors = validate_playbook_schema(playbook)
    if not is_valid:
        raise PlaybookValidationError(f"Playbook inválido: {'; '.join(errors)}")

    cfg_path = pathlib.Path(target_yaml_path)
    if not cfg_path.is_file():
        raise FileNotFoundError(f"target.yaml no encontrado en: {cfg_path}")

    auth_config = {}
    parsed: Dict[str, Any] = {}
    content = cfg_path.read_text(encoding="utf-8")
    scope_valid = True
    scope_error_msg = None

    try:
        from seclab_scope import load_target_yaml, ScopeError
        try:
            parsed = load_target_yaml(cfg_path)
            if not isinstance(parsed, dict) or not isinstance(parsed.get("scope"), dict):
                scope_valid = False
                scope_error_msg = "El contrato de alcance requiere un objeto 'scope' válido."
            else:
                auth_config = parsed.get("authorization", {})
        except ScopeError as se:
            scope_valid = False
            scope_error_msg = str(se)
    except ImportError:
        # Fallback fail-closed si el módulo seclab_scope no puede ser importado
        scope_valid = False
        scope_error_msg = "Módulo seclab_scope no disponible para validación de alcance (fail-closed)."

    if not scope_valid:
        steps_eval: List[Dict[str, Any]] = []
        block_msg = f"Acción bloqueada: target.yaml no contiene un contrato de alcance válido ({scope_error_msg})."
        for step in playbook["steps"]:
            steps_eval.append({
                "step_id": step.get("id"),
                "title": step.get("title", step.get("id")),
                "interaction_type": step.get("interaction_type"),
                "status": "BLOCKED",
                "reason": block_msg,
            })
        return {
            "playbook_id": playbook.get("id"),
            "title": playbook.get("title"),
            "can_execute": False,
            "total_steps": len(playbook["steps"]),
            "blocked_steps_count": len(playbook["steps"]),
            "authorization_state": {
                "allow_passive": False,
                "allow_active": False,
            },
            "scope_data": None,
            "scope_error": block_msg,
            "steps_evaluation": steps_eval,
        }

    allow_passive = bool(auth_config.get("allow_passive", False))
    allow_active = bool(auth_config.get("allow_active", False))
    active_block_reason = "Acción activa bloqueada: el contrato de alcance (target.yaml) tiene 'allow_active: false'."
    passive_block_reason = "Acción pasiva bloqueada: el contrato de alcance (target.yaml) tiene 'allow_passive: false'."

    # B2: Validación canónica universal de autorización y vigencia temporal (fail-closed)
    current_time = now or datetime.now(timezone.utc)
    try:
        from seclab_scope import require_authorization, ScopeError
        if allow_passive:
            try:
                require_authorization(parsed, "passive", now=current_time)
            except ScopeError as se:
                allow_passive = False
                passive_block_reason = f"Acción pasiva bloqueada: {se}"
        if allow_active:
            try:
                require_authorization(parsed, "active", now=current_time)
            except ScopeError as se:
                allow_active = False
                active_block_reason = f"Acción activa bloqueada: {se}"
    except ImportError:
        pass

    # B3: Cargar funciones de Scope Guard para comprobación de parámetros si se proporcionan
    try:
        from seclab_scope import check_scope, ScopeError
    except ImportError:
        check_scope = None

    steps_eval: List[Dict[str, Any]] = []
    can_execute = True
    blocked_count = 0

    params = parameters or {}
    engagement_dir = str(cfg_path.parent)

    for step in playbook["steps"]:
        s_id = step["id"]
        itype = step["interaction_type"]
        req_perms = step.get("required_permissions") or []

        status = "AUTHORIZED"
        reason = "Paso autorizado por el alcance actual."

        if itype in ("active_low", "active_high") and not allow_active:
            status = "BLOCKED"
            reason = active_block_reason
            can_execute = False
            blocked_count += 1
        elif itype == "passive" and not allow_passive:
            status = "BLOCKED"
            reason = passive_block_reason
            can_execute = False
            blocked_count += 1
        elif "active" in req_perms and not allow_active:
            status = "BLOCKED"
            reason = active_block_reason if active_block_reason != "Acción activa bloqueada: el contrato de alcance (target.yaml) tiene 'allow_active: false'." else "Permiso 'active' requerido pero no autorizado en target.yaml."
            can_execute = False
            blocked_count += 1
        else:
            # B3: Extraer destinos para este paso específico y evaluar contra Scope Guard
            step_targets, step_missing_err = extract_step_targets(
                step,
                context={
                    "parameters": params,
                    "target_yaml_path": cfg_path,
                    "engagement_dir": engagement_dir,
                },
                dry_run=True,
            )
            target_selector = step.get("target_selector")
            is_active_step = itype in ("active_low", "active_high") or "active" in req_perms
            has_declared_source = step_has_declared_target_source(step)
            has_dynamic_targets = step_has_unverified_dynamic_targets(step.get("command_template", ""))
            unexpanded_target_placeholders = [
                p for p in re.findall(r"\{([a-zA-Z0-9_]+)\}", step.get("command_template", ""))
                if is_target_placeholder(p, step.get("command_template", "")) and (not params or p not in params or params[p] is None or str(params[p]).strip() == "")
            ]

            if is_active_step and has_dynamic_targets:
                status = "BLOCKED"
                reason = "El paso activo contiene destinos dinámicos o sustituciones de shell no verificables contra Scope Guard."
                can_execute = False
                blocked_count += 1
            elif step_missing_err:
                status = "BLOCKED"
                reason = f"Error en archivos de objetivos: {step_missing_err}"
                can_execute = False
                blocked_count += 1
            elif target_selector in ("in_scope_domains", "in_scope_ips") and not step_targets:
                status = "BLOCKED"
                reason = f"El paso requiere un selector de objetivos '{target_selector}' pero no se resolvieron destinos en alcance."
                can_execute = False
                blocked_count += 1
            elif is_active_step and unexpanded_target_placeholders:
                status = "BLOCKED"
                reason = f"El paso activo contiene placeholders de destino sin resolver: {', '.join(unexpanded_target_placeholders)}."
                can_execute = False
                blocked_count += 1
            elif is_active_step and not has_declared_source:
                status = "BLOCKED"
                reason = "El paso activo requiere un objetivo verificable contra Scope Guard pero no declara una fuente de destino resoluble."
                can_execute = False
                blocked_count += 1
            elif is_active_step and not step_targets:
                status = "BLOCKED"
                reason = "El paso activo requiere al menos un objetivo resoluble y verificable contra Scope Guard pero no produjo ningún candidato."
                can_execute = False
                blocked_count += 1
            elif check_scope is None:
                status = "BLOCKED"
                reason = "Módulo seclab_scope no disponible para comprobar destinos contra Scope Guard."
                can_execute = False
                blocked_count += 1
            elif isinstance(parsed, dict) and step_targets:
                for target_val in step_targets:
                    try:
                        verdict, v_reason = check_scope(target_val, parsed)
                    except ScopeError as se:
                        verdict, v_reason = "UNKNOWN", str(se)
                    if verdict != "IN_SCOPE":
                        status = "BLOCKED"
                        reason = f"Destino '{target_val}' fuera de alcance según Scope Guard ({verdict}: {v_reason})."
                        can_execute = False
                        blocked_count += 1
                        break

        steps_eval.append({
            "step_id": s_id,
            "title": step.get("title", s_id),
            "interaction_type": itype,
            "status": status,
            "reason": reason,
        })

    return {
        "playbook_id": playbook.get("id"),
        "title": playbook.get("title"),
        "can_execute": can_execute,
        "total_steps": len(playbook["steps"]),
        "blocked_steps_count": blocked_count,
        "authorization_state": {
            "allow_passive": allow_passive,
            "allow_active": allow_active,
        },
        "scope_data": parsed,
        "steps_evaluation": steps_eval,
    }


DANGEROUS_PARAM_CHARS = set(";&|`$\n\r")


def interpolate_command(template: str, params: Dict[str, Any]) -> str:
    """Interpola de forma segura parámetros en la plantilla del comando.
    
    Rechaza valores que contengan metacaracteres de inyección de shell.
    """
    for key, val in params.items():
        val_str = str(val)
        if any(c in val_str for c in DANGEROUS_PARAM_CHARS):
            raise PlaybookValidationError(
                f"Parámetro '{key}' contiene caracteres no permitidos para comando: '{val_str}'"
            )
        placeholder = f"{{{key}}}"
        template = template.replace(placeholder, val_str)
    return template


def execute_playbook_step(
    step: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None,
    dry_run: bool = True,
) -> Dict[str, Any]:
    """Ejecuta o simula un paso de playbook determinista.
    
    Verifica que el paso esté autorizado en el contexto y aplica dry_run de forma segura.
    """
    ctx = context or {}
    params = ctx.get("parameters") or {}
    allow_passive = bool(ctx.get("allow_passive", False))
    allow_active = bool(ctx.get("allow_active", False))
    scope_data = ctx.get("scope_data")

    step_id = step.get("id", "unknown_step")
    title = step.get("title", step_id)
    itype = step.get("interaction_type", "passive")
    cmd_tpl = step.get("command_template", "")
    timeout = step.get("timeout_seconds", 300)
    expected_outputs = step.get("expected_outputs", [])

    # B1 & B3: En ejecución real, se exige un contrato canónico de alcance (scope en target.yaml) y permisos explícitos (fail-closed)
    if not dry_run:
        if not scope_data or not isinstance(scope_data, dict) or not isinstance(scope_data.get("scope"), dict):
            return {
                "step_id": step_id,
                "title": title,
                "interaction_type": itype,
                "status": "BLOCKED",
                "command": cmd_tpl,
                "exit_code": 126,
                "output": "Bloqueado: Se requiere un contrato de alcance válido (scope en target.yaml) para la ejecución real.",
                "expected_outputs": expected_outputs,
                "stop_condition_met": True,
                "is_simulated": False,
            }

        if itype in ("active_low", "active_high") and not allow_active:
            return {
                "step_id": step_id,
                "title": title,
                "interaction_type": itype,
                "status": "BLOCKED",
                "command": cmd_tpl,
                "exit_code": 126,
                "output": "Bloqueado: La interacción activa no está autorizada en el contrato de alcance.",
                "expected_outputs": expected_outputs,
                "stop_condition_met": True,
                "is_simulated": False,
            }

        if itype == "passive" and not allow_passive:
            return {
                "step_id": step_id,
                "title": title,
                "interaction_type": itype,
                "status": "BLOCKED",
                "command": cmd_tpl,
                "exit_code": 126,
                "output": "Bloqueado: La interacción pasiva no está autorizada en el contrato de alcance.",
                "expected_outputs": expected_outputs,
                "stop_condition_met": True,
                "is_simulated": False,
            }

        # B2: Validación adicional en profundidad de contrato de autorización y vigencia
        if scope_data and isinstance(scope_data, dict) and "authorization" in scope_data:
            try:
                from seclab_scope import require_authorization, ScopeError
                if itype in ("active_low", "active_high"):
                    require_authorization(scope_data, "active")
                elif itype == "passive":
                    require_authorization(scope_data, "passive")
            except ScopeError as se:
                return {
                    "step_id": step_id,
                    "title": title,
                    "interaction_type": itype,
                    "status": "BLOCKED",
                    "command": cmd_tpl,
                    "exit_code": 126,
                    "output": f"Bloqueado: {se}",
                    "expected_outputs": expected_outputs,
                    "stop_condition_met": True,
                    "is_simulated": False,
                }
    else:
        # En simulación previa (dry_run), evaluar contra contexto si está configurado
        if itype in ("active_low", "active_high") and not allow_active and "allow_active" in ctx:
            return {
                "step_id": step_id,
                "title": title,
                "interaction_type": itype,
                "status": "BLOCKED",
                "command": cmd_tpl,
                "exit_code": 126,
                "output": "Bloqueado: La interacción activa no está autorizada en el contrato de alcance.",
                "expected_outputs": expected_outputs,
                "stop_condition_met": True,
                "is_simulated": True,
            }

        if itype == "passive" and not allow_passive and "allow_passive" in ctx:
            return {
                "step_id": step_id,
                "title": title,
                "interaction_type": itype,
                "status": "BLOCKED",
                "command": cmd_tpl,
                "exit_code": 126,
                "output": "Bloqueado: La interacción pasiva no está autorizada en el contrato de alcance.",
                "expected_outputs": expected_outputs,
                "stop_condition_met": True,
                "is_simulated": True,
            }

    # B3: Cargar funciones de Scope Guard para comprobación de parámetros si se proporcionan
    try:
        from seclab_scope import check_scope, ScopeError
    except ImportError:
        check_scope = None

    target_selector = step.get("target_selector")
    target_candidates, missing_file_err = extract_step_targets(step, context=ctx, dry_run=dry_run)
    is_active_step = itype in ("active_low", "active_high") or "active" in (step.get("required_permissions") or [])
    unexpanded_target_placeholders = [
        p for p in re.findall(r"\{([a-zA-Z0-9_]+)\}", cmd_tpl)
        if is_target_placeholder(p, cmd_tpl) and (not params or p not in params or params[p] is None or str(params[p]).strip() == "")
    ]

    if not dry_run and is_active_step and step_has_unverified_dynamic_targets(cmd_tpl):
        return {
            "step_id": step_id,
            "title": title,
            "interaction_type": itype,
            "status": "BLOCKED",
            "command": cmd_tpl,
            "exit_code": 126,
            "output": "Bloqueado: El paso activo contiene destinos dinámicos o sustituciones de shell no verificables contra Scope Guard.",
            "expected_outputs": expected_outputs,
            "stop_condition_met": True,
            "is_simulated": False,
        }

    if missing_file_err and not dry_run:
        return {
            "step_id": step_id,
            "title": title,
            "interaction_type": itype,
            "status": "BLOCKED",
            "command": cmd_tpl,
            "exit_code": 126,
            "output": f"Bloqueado: {missing_file_err}",
            "expected_outputs": expected_outputs,
            "stop_condition_met": True,
            "is_simulated": False,
        }

    if not dry_run and check_scope is None:
        return {
            "step_id": step_id,
            "title": title,
            "interaction_type": itype,
            "status": "BLOCKED",
            "command": cmd_tpl,
            "exit_code": 126,
            "output": "Bloqueado: Módulo de seguridad Scope Guard (seclab_scope) no disponible para ejecución real.",
            "expected_outputs": expected_outputs,
            "stop_condition_met": True,
            "is_simulated": False,
        }

    if not dry_run and target_selector in ("in_scope_domains", "in_scope_ips") and not target_candidates:
        return {
            "step_id": step_id,
            "title": title,
            "interaction_type": itype,
            "status": "BLOCKED",
            "command": cmd_tpl,
            "exit_code": 126,
            "output": f"Bloqueado: El paso requiere el selector '{target_selector}' pero no se encontraron destinos en alcance.",
            "expected_outputs": expected_outputs,
            "stop_condition_met": True,
            "is_simulated": False,
        }

    if not dry_run and is_active_step and unexpanded_target_placeholders:
        return {
            "step_id": step_id,
            "title": title,
            "interaction_type": itype,
            "status": "BLOCKED",
            "command": cmd_tpl,
            "exit_code": 126,
            "output": f"Bloqueado: El paso activo contiene placeholders de destino sin resolver ({', '.join(unexpanded_target_placeholders)}).",
            "expected_outputs": expected_outputs,
            "stop_condition_met": True,
            "is_simulated": False,
        }

    if not dry_run and is_active_step and not target_candidates:
        return {
            "step_id": step_id,
            "title": title,
            "interaction_type": itype,
            "status": "BLOCKED",
            "command": cmd_tpl,
            "exit_code": 126,
            "output": "Bloqueado: El paso activo requiere un objetivo verificable contra Scope Guard pero no declara ni resuelve ningún destino.",
            "expected_outputs": expected_outputs,
            "stop_condition_met": True,
            "is_simulated": False,
        }

    if scope_data and isinstance(scope_data, dict) and check_scope is not None and target_candidates:
        for candidate in target_candidates:
            try:
                verdict, reason = check_scope(candidate, scope_data)
            except ScopeError as se:
                verdict, reason = "UNKNOWN", str(se)
            if verdict != "IN_SCOPE":
                return {
                    "step_id": step_id,
                    "title": title,
                    "interaction_type": itype,
                    "status": "BLOCKED",
                    "command": cmd_tpl,
                    "exit_code": 126,
                    "output": f"Bloqueado por Scope Guard: El objetivo '{candidate}' no está autorizado en el alcance ({verdict}: {reason}).",
                    "expected_outputs": expected_outputs,
                    "stop_condition_met": True,
                    "is_simulated": dry_run,
                }

    try:
        cmd = interpolate_command(cmd_tpl, params)
    except PlaybookValidationError as e:
        return {
            "step_id": step_id,
            "title": title,
            "interaction_type": itype,
            "status": "ERROR",
            "command": cmd_tpl,
            "exit_code": 1,
            "output": f"Error de interpolación: {e}",
            "expected_outputs": expected_outputs,
            "stop_condition_met": True,
            "is_simulated": dry_run,
        }

    # Salvaguarda fail-closed: verificar que el comando interpolado no contenga destinos fuera de alcance
    if not dry_run and is_active_step and scope_data and check_scope is not None:
        for lit in _extract_literal_targets(cmd):
            try:
                verdict, reason = check_scope(lit, scope_data)
            except ScopeError as se:
                verdict, reason = "UNKNOWN", str(se)
            if verdict != "IN_SCOPE":
                return {
                    "step_id": step_id,
                    "title": title,
                    "interaction_type": itype,
                    "status": "BLOCKED",
                    "command": cmd_tpl,
                    "exit_code": 126,
                    "output": f"Bloqueado por Scope Guard: El objetivo interpolado '{lit}' no está autorizado en el alcance ({verdict}: {reason}).",
                    "expected_outputs": expected_outputs,
                    "stop_condition_met": True,
                    "is_simulated": False,
                }

    if dry_run:
        return {
            "step_id": step_id,
            "title": title,
            "interaction_type": itype,
            "status": "SIMULATED",
            "command": cmd,
            "exit_code": 0,
            "output": f"[dry-run] Simulación de paso '{step_id}' completada.",
            "expected_outputs": expected_outputs,
            "stop_condition_met": False,
            "is_simulated": True,
        }

    # Modo ejecución real acotada
    try:
        proc = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        out = (proc.stdout + proc.stderr)[:131072]
        status = "SUCCESS" if proc.returncode == 0 else "FAILED"
        return {
            "step_id": step_id,
            "title": title,
            "interaction_type": itype,
            "status": status,
            "command": cmd,
            "exit_code": proc.returncode,
            "output": out,
            "expected_outputs": expected_outputs,
            "stop_condition_met": proc.returncode != 0,
            "is_simulated": False,
        }
    except subprocess.TimeoutExpired:
        return {
            "step_id": step_id,
            "title": title,
            "interaction_type": itype,
            "status": "TIMEOUT",
            "command": cmd,
            "exit_code": 124,
            "output": f"Tiempo de espera agotado ({timeout}s).",
            "expected_outputs": expected_outputs,
            "stop_condition_met": True,
            "is_simulated": False,
        }
    except Exception as e:
        return {
            "step_id": step_id,
            "title": title,
            "interaction_type": itype,
            "status": "ERROR",
            "command": cmd,
            "exit_code": 1,
            "output": f"Error al ejecutar paso: {e}",
            "expected_outputs": expected_outputs,
            "stop_condition_met": True,
            "is_simulated": False,
        }


def run_playbook(
    playbook_data: Dict[str, Any],
    target_yaml_path: Optional[Union[str, pathlib.Path]] = None,
    context: Optional[Dict[str, Any]] = None,
    dry_run: bool = True,
    max_steps: Optional[int] = None,
) -> Dict[str, Any]:
    """Ejecuta secuencialmente los pasos de un playbook con salvaguardas y parada determinista."""
    ctx = dict(context or {})

    # Si se pasa target_yaml_path, extraer autorizaciones
    if target_yaml_path:
        ctx.setdefault("target_yaml_path", str(target_yaml_path))
        ctx.setdefault("engagement_dir", str(pathlib.Path(target_yaml_path).parent.resolve()))
        scope_eval = validate_playbook_against_scope(
            playbook=playbook_data,
            target_yaml_path=target_yaml_path,
            parameters=ctx.get("parameters"),
        )
        ctx["allow_passive"] = scope_eval["authorization_state"]["allow_passive"]
        ctx["allow_active"] = scope_eval["authorization_state"]["allow_active"]
        ctx["scope_data"] = scope_eval.get("scope_data")
        if not dry_run and not scope_eval["can_execute"]:
            return {
                "playbook_id": playbook_data.get("id"),
                "title": playbook_data.get("title"),
                "status": "BLOCKED",
                "can_execute": False,
                "reason": scope_eval.get("scope_error") or "El playbook contiene pasos activos o no autorizados por target.yaml.",
                "total_steps": len(playbook_data.get("steps", [])),
                "executed_steps_count": 0,
                "dry_run": dry_run,
                "steps_results": [],
            }
    elif not dry_run:
        # B1: Rechazo fail-closed inmediato en ejecución real sin target.yaml
        return {
            "playbook_id": playbook_data.get("id"),
            "title": playbook_data.get("title"),
            "status": "BLOCKED",
            "can_execute": False,
            "reason": "Ejecución real denegada: se requiere un proyecto y un contrato de alcance (target.yaml) válidos.",
            "total_steps": len(playbook_data.get("steps", [])),
            "executed_steps_count": 0,
            "dry_run": False,
            "steps_results": [],
        }
    elif dry_run:
        # En simulación previa sin target.yaml (previsualización de plantilla),
        # se permite la simulación determinista sin tráfico real
        ctx.setdefault("allow_passive", True)
        ctx.setdefault("allow_active", True)

    steps = playbook_data.get("steps", [])
    if max_steps is not None:
        steps = steps[:max_steps]

    steps_results: List[Dict[str, Any]] = []
    overall_status = "COMPLETED" if not dry_run else "SIMULATED"

    for step in steps:
        res = execute_playbook_step(step, context=ctx, dry_run=dry_run)
        steps_results.append(res)
        if res.get("stop_condition_met") or res.get("status") in ("BLOCKED", "FAILED", "ERROR", "TIMEOUT"):
            if res.get("status") == "BLOCKED":
                overall_status = "BLOCKED"
            else:
                overall_status = "STOPPED"
            break

    return {
        "playbook_id": playbook_data.get("id"),
        "title": playbook_data.get("title"),
        "status": overall_status,
        "dry_run": dry_run,
        "total_steps": len(playbook_data.get("steps", [])),
        "executed_steps_count": len(steps_results),
        "steps_results": steps_results,
    }


def save_playbook_run_evidence(
    engagement_dir: Union[str, pathlib.Path],
    run_result: Dict[str, Any],
    parameters: Optional[Dict[str, Any]] = None,
) -> pathlib.Path:
    """Guarda el resultado de ejecución o simulación de un playbook como evidencia de auditoría.

    Ruta canónica: evidence/playbooks/<playbook_id>_<timestamp>.json
    Genera atómicamente el archivo estructurado de evidencia con metadatos completos.
    """
    eng_dir = pathlib.Path(engagement_dir).resolve()
    if not eng_dir.is_dir():
        raise FileNotFoundError(f"Directorio de engagement no encontrado: {eng_dir}")

    playbooks_ev_dir = eng_dir / "evidence" / "playbooks"
    playbooks_ev_dir.mkdir(parents=True, exist_ok=True)

    raw_id = str(run_result.get("playbook_id") or "unnamed_playbook")
    safe_id = re.sub(r"[^a-zA-Z0-9_.-]", "_", raw_id)

    now_utc = datetime.now(timezone.utc)
    ts_str = now_utc.strftime("%Y%m%dT%H%M%SZ")
    iso_str = now_utc.isoformat()

    file_name = f"{safe_id}_{ts_str}.json"
    target_file = playbooks_ev_dir / file_name

    evidence_data = {
        "schema_version": "1.0",
        "evidence_type": "playbook_run",
        "playbook_id": raw_id,
        "playbook_title": run_result.get("title", raw_id),
        "timestamp": iso_str,
        "status": run_result.get("status", "UNKNOWN"),
        "dry_run": bool(run_result.get("dry_run", True)),
        "parameters": parameters or {},
        "total_steps": run_result.get("total_steps", 0),
        "executed_steps_count": run_result.get("executed_steps_count", 0),
        "steps_results": run_result.get("steps_results", []),
    }

    tmp_file = playbooks_ev_dir / f".tmp_{file_name}.{os.getpid()}"
    try:
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(evidence_data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_file, target_file)
    except Exception:
        if tmp_file.exists():
            try:
                tmp_file.unlink()
            except OSError:
                pass
        raise

    return target_file


def list_playbook_runs(
    engagement_dir: Union[str, pathlib.Path],
    playbook_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Lista las ejecuciones de playbooks registradas como evidencia en el engagement.

    Retorna una lista ordenada de ejecuciones (más recientes primero).
    """
    eng_dir = pathlib.Path(engagement_dir).resolve()
    playbooks_ev_dir = eng_dir / "evidence" / "playbooks"
    if not playbooks_ev_dir.is_dir():
        return []

    runs: List[Dict[str, Any]] = []
    for f in sorted(playbooks_ev_dir.glob("*.json"), reverse=True):
        if not f.is_file() or f.name.startswith("."):
            continue
        try:
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            if not isinstance(data, dict):
                continue

            p_id = data.get("playbook_id")
            if playbook_id and p_id != playbook_id:
                continue

            runs.append({
                "playbook_id": p_id,
                "playbook_title": data.get("playbook_title", p_id),
                "timestamp": data.get("timestamp", ""),
                "status": data.get("status", "UNKNOWN"),
                "dry_run": data.get("dry_run", True),
                "total_steps": data.get("total_steps", 0),
                "executed_steps_count": data.get("executed_steps_count", 0),
                "file_name": f.name,
                "relative_path": str(f.relative_to(eng_dir)),
            })
        except Exception:
            continue

    return runs


