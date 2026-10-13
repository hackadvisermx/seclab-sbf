#!/usr/bin/env python3
"""Gestor, Schema y Validador de Playbooks Deterministas para SecLab-SBF (V3-04).

Define el esquema canónico para procedimientos reproducibles de auditoría (Playbooks),
valida la estructura de pasos, parámetros y condiciones de parada, y comprueba que
los permisos requeridos (pasivos/activos) estén autorizados contra el contrato de
alcance (target.yaml) antes de cualquier ejecución.

Sin dependencias externas obligatorias (Python 3 stdlib + yaml si disponible).
"""

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
    "proxy",
    "user_agent",
    "cookie",
    "header",
    "headers",
    "port",
    "ports",
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
}


def extract_step_targets(
    step: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None,
    dry_run: bool = True,
) -> Tuple[List[str], Optional[str]]:
    """Extrae de manera exhaustiva todos los destinos que consumirá un paso.
    
    Inspecciona:
    1. Placeholders en command_template que provienen de parameters (excluyendo flags operacionales).
    2. Parámetros provistos con nombres canónicos de destino (target, domain, endpoint, etc.).
    3. Archivos referenciados por target_selector o inputs (ej. recon/subdomains.txt).
    
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
        p_lower = p.lower()
        if p_lower not in NON_TARGET_PLACEHOLDERS and p in params and params[p] is not None:
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

    # 3. Selectores o insumos basados en archivos (ej. recon/subdomains.txt)
    file_candidates: List[str] = []
    if target_selector and (
        target_selector.endswith((".txt", ".lst", ".csv", ".json"))
        or "/" in target_selector
        or "\\" in target_selector
    ) and target_selector not in ("in_scope_domains", "in_scope_ips", "local_gateway"):
        file_candidates.append(target_selector)

    for inp in inputs:
        if isinstance(inp, str):
            inp_clean = inp.strip()
            if (
                inp_clean.endswith((".txt", ".lst", ".csv"))
                and inp_clean not in ("target.yaml", "scope.txt")
                and inp_clean not in file_candidates
            ):
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
                if not lines and not dry_run:
                    missing_file_error = f"El archivo de objetivos '{f_rel}' está vacío."
                for line in lines:
                    if line not in targets:
                        targets.append(line)
            except Exception as e:
                if not dry_run:
                    missing_file_error = f"Error al leer archivo de objetivos '{f_rel}': {e}"
        elif not dry_run:
            missing_file_error = f"El archivo de objetivos '{f_rel}' no existe en el proyecto."

    return targets, missing_file_error


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
    try:
        from seclab_scope import load_target_yaml
        parsed = load_target_yaml(cfg_path)
        if isinstance(parsed, dict):
            auth_config = parsed.get("authorization", {})
    except Exception:
        if yaml is not None:
            try:
                parsed = yaml.safe_load(content) or {}
                if isinstance(parsed, dict):
                    auth_config = parsed.get("authorization", {})
            except Exception:
                pass
        else:
            # Extracción básica de expresiones clave si PyYAML no está presente
            for line in content.splitlines():
                line = line.strip()
                if line.startswith("allow_active:"):
                    auth_config["allow_active"] = "true" in line.lower()
                elif line.startswith("allow_passive:"):
                    auth_config["allow_passive"] = "true" in line.lower()
                elif line.startswith("valid_from:"):
                    auth_config["valid_from"] = line.split(":", 1)[1].strip().strip("'\"")
                elif line.startswith("valid_until:"):
                    auth_config["valid_until"] = line.split(":", 1)[1].strip().strip("'\"")
                elif line.startswith("reference:"):
                    auth_config["reference"] = line.split(":", 1)[1].strip().strip("'\"")
            parsed = {"authorization": auth_config}

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
            if check_scope is not None and isinstance(parsed, dict) and step_targets:
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

    # B1: En ejecución real, se exige que las interacciones estén explícitamente autorizadas (fail-closed)
    if not dry_run:
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
    elif not dry_run and target_selector in ("in_scope_domains", "in_scope_ips") and not scope_data:
        return {
            "step_id": step_id,
            "title": title,
            "interaction_type": itype,
            "status": "BLOCKED",
            "command": cmd_tpl,
            "exit_code": 126,
            "output": "Bloqueado: Se requiere un contrato de alcance (target.yaml) para validar el selector de objetivos.",
            "expected_outputs": expected_outputs,
            "stop_condition_met": True,
            "is_simulated": False,
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
                "reason": "El playbook contiene pasos activos o no autorizados por target.yaml.",
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


