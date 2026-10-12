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


def validate_playbook_against_scope(
    playbook: Dict[str, Any],
    target_yaml_path: Union[str, pathlib.Path],
) -> Dict[str, Any]:
    """Evalúa los permisos de cada paso del playbook contra la autorización de target.yaml.
    
    Verifica que las interacciones activas ('active_low', 'active_high') cuenten con
    'allow_active: true' y las pasivas con 'allow_passive: true' en el target.yaml.
    """
    is_valid, errors = validate_playbook_schema(playbook)
    if not is_valid:
        raise PlaybookValidationError(f"Playbook inválido: {'; '.join(errors)}")

    cfg_path = pathlib.Path(target_yaml_path)
    if not cfg_path.is_file():
        raise FileNotFoundError(f"target.yaml no encontrado en: {cfg_path}")

    auth_config = {}
    content = cfg_path.read_text(encoding="utf-8")
    if yaml is not None:
        try:
            parsed = yaml.safe_load(content) or {}
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

    allow_passive = bool(auth_config.get("allow_passive", False))
    allow_active = bool(auth_config.get("allow_active", False))

    steps_eval: List[Dict[str, Any]] = []
    can_execute = True
    blocked_count = 0

    for step in playbook["steps"]:
        s_id = step["id"]
        itype = step["interaction_type"]
        req_perms = step.get("required_permissions") or []

        status = "AUTHORIZED"
        reason = "Paso autorizado por el alcance actual."

        if itype in ("active_low", "active_high") and not allow_active:
            status = "BLOCKED"
            reason = "Acción activa bloqueada: el contrato de alcance (target.yaml) tiene 'allow_active: false'."
            can_execute = False
            blocked_count += 1
        elif itype == "passive" and not allow_passive:
            status = "BLOCKED"
            reason = "Acción pasiva bloqueada: el contrato de alcance (target.yaml) tiene 'allow_passive: false'."
            can_execute = False
            blocked_count += 1
        elif "active" in req_perms and not allow_active:
            status = "BLOCKED"
            reason = "Permiso 'active' requerido pero no autorizado en target.yaml."
            can_execute = False
            blocked_count += 1

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
        "steps_evaluation": steps_eval,
    }
