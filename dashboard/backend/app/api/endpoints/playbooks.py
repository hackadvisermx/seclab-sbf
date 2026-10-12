import pathlib
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from app.config import REPO_ROOT, WORKSPACE_DIR
from seclab_playbook import (
    load_playbook_file,
    validate_playbook_schema,
    validate_playbook_against_scope,
    run_playbook,
    execute_playbook_step,
    save_playbook_run_evidence,
    list_playbook_runs,
    PlaybookValidationError,
)

router = APIRouter(prefix="/playbooks", tags=["Playbooks Deterministas"])


def _get_playbook_dirs(target_dir: Optional[pathlib.Path] = None) -> List[pathlib.Path]:
    dirs = [
        REPO_ROOT / "workspace-seed" / "playbooks",
        pathlib.Path("/usr/local/share/seclab/playbooks"),
        WORKSPACE_DIR / "playbooks",
    ]
    if target_dir:
        dirs.insert(0, target_dir / "playbooks")
    return [d for d in dirs if d.is_dir()]


class PlaybookValidateRequest(BaseModel):
    playbook: Dict[str, Any]
    engagement_id: Optional[str] = None
    type: str = "engagement"


@router.get("")
def list_playbooks(engagement_id: Optional[str] = None, type: str = "engagement"):
    """Lista todos los playbooks disponibles (semilla de fábrica y personalizados del proyecto)."""
    target_dir = None
    if engagement_id:
        target_dir = WORKSPACE_DIR / ("retos" if type == "reto" else "engagements") / engagement_id

    playbooks = []
    seen_ids = set()

    for p_dir in _get_playbook_dirs(target_dir):
        for f in sorted(p_dir.glob("*.yaml")) + sorted(p_dir.glob("*.yml")):
            if f.is_file():
                try:
                    pb = load_playbook_file(f)
                    pb_id = pb.get("id")
                    if pb_id and pb_id not in seen_ids:
                        seen_ids.add(pb_id)
                        is_valid, _ = validate_playbook_schema(pb)
                        playbooks.append({
                            "id": pb_id,
                            "title": pb.get("title", f.stem),
                            "version": pb.get("version", "1.0"),
                            "category": pb.get("category", "general"),
                            "description": pb.get("description", ""),
                            "author": pb.get("author", ""),
                            "steps_count": len(pb.get("steps", [])),
                            "is_valid": is_valid,
                            "file_path": str(f.name),
                        })
                except Exception:
                    continue

    return playbooks


@router.get("/{playbook_id}")
def get_playbook(playbook_id: str, engagement_id: Optional[str] = None, type: str = "engagement"):
    """Devuelve la definición completa de un playbook por su ID."""
    target_dir = None
    if engagement_id:
        target_dir = WORKSPACE_DIR / ("retos" if type == "reto" else "engagements") / engagement_id

    for p_dir in _get_playbook_dirs(target_dir):
        for f in sorted(p_dir.glob("*.yaml")) + sorted(p_dir.glob("*.yml")):
            if f.is_file():
                try:
                    pb = load_playbook_file(f)
                    if pb.get("id") == playbook_id:
                        is_valid, errors = validate_playbook_schema(pb)
                        return {
                            "playbook": pb,
                            "is_valid": is_valid,
                            "errors": errors,
                        }
                except Exception:
                    continue

    raise HTTPException(status_code=404, detail=f"Playbook '{playbook_id}' no encontrado.")


@router.post("/validate")
def validate_playbook(payload: PlaybookValidateRequest):
    """Valida un playbook contra el esquema formal y contra el contrato de alcance si se indica un engagement."""
    is_valid, errors = validate_playbook_schema(payload.playbook)
    if not is_valid:
        return {
            "is_valid": False,
            "errors": errors,
            "scope_evaluation": None,
        }

    scope_eval = None
    if payload.engagement_id:
        target_dir = WORKSPACE_DIR / ("retos" if payload.type == "reto" else "engagements") / payload.engagement_id
        target_yaml = target_dir / "target.yaml"
        if target_yaml.is_file():
            scope_eval = validate_playbook_against_scope(payload.playbook, target_yaml)
        else:
            scope_eval = {
                "can_execute": False,
                "error": f"Falta target.yaml en {payload.engagement_id}",
            }

    return {
        "is_valid": True,
        "errors": [],
        "scope_evaluation": scope_eval,
    }


class PlaybookRunRequest(BaseModel):
    engagement_id: Optional[str] = None
    type: str = "engagement"
    parameters: Optional[Dict[str, Any]] = None
    dry_run: bool = True
    max_steps: Optional[int] = None
    save_evidence: bool = True


@router.get("/runs/all")
def get_all_playbook_runs(engagement_id: str = Query(...), type: str = "engagement"):
    """Lista todas las ejecuciones registradas de playbooks como evidencia en el engagement."""
    target_dir = WORKSPACE_DIR / ("retos" if type == "reto" else "engagements") / engagement_id
    if not target_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Engagement '{engagement_id}' no encontrado.")
    return list_playbook_runs(target_dir)


@router.get("/{playbook_id}/runs")
def get_playbook_runs_endpoint(playbook_id: str, engagement_id: str = Query(...), type: str = "engagement"):
    """Lista las ejecuciones registradas para un playbook específico en el engagement."""
    target_dir = WORKSPACE_DIR / ("retos" if type == "reto" else "engagements") / engagement_id
    if not target_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Engagement '{engagement_id}' no encontrado.")
    return list_playbook_runs(target_dir, playbook_id=playbook_id)


@router.post("/{playbook_id}/run")
def run_playbook_endpoint(playbook_id: str, payload: PlaybookRunRequest):
    """Ejecuta o simula (dry-run) un playbook determinista para el engagement indicado."""
    target_dir = None
    target_yaml = None
    if payload.engagement_id:
        target_dir = WORKSPACE_DIR / ("retos" if payload.type == "reto" else "engagements") / payload.engagement_id
        target_yaml = target_dir / "target.yaml"

    playbook_data = None
    for p_dir in _get_playbook_dirs(target_dir):
        for f in sorted(p_dir.glob("*.yaml")) + sorted(p_dir.glob("*.yml")):
            if f.is_file():
                try:
                    pb = load_playbook_file(f)
                    if pb.get("id") == playbook_id:
                        playbook_data = pb
                        break
                except Exception:
                    continue
        if playbook_data:
            break

    if not playbook_data:
        raise HTTPException(status_code=404, detail=f"Playbook '{playbook_id}' no encontrado.")

    context = {
        "parameters": payload.parameters or {},
    }

    try:
        result = run_playbook(
            playbook_data=playbook_data,
            target_yaml_path=target_yaml if (target_yaml and target_yaml.is_file()) else None,
            context=context,
            dry_run=payload.dry_run,
            max_steps=payload.max_steps,
        )
        if payload.save_evidence and target_dir and target_dir.is_dir():
            try:
                ev_file = save_playbook_run_evidence(
                    engagement_dir=target_dir,
                    run_result=result,
                    parameters=payload.parameters,
                )
                result["evidence_file"] = str(ev_file.relative_to(target_dir))
            except Exception as e:
                result["evidence_file_error"] = str(e)

        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error en la ejecución del playbook: {e}")


class PlaybookStepRunRequest(BaseModel):
    step_id: str
    engagement_id: Optional[str] = None
    type: str = "engagement"
    parameters: Optional[Dict[str, Any]] = None
    dry_run: bool = True


@router.post("/{playbook_id}/step/run")
def run_playbook_step_endpoint(playbook_id: str, payload: PlaybookStepRunRequest):
    """Ejecuta o simula un paso específico individual de un playbook determinista."""
    target_dir = None
    target_yaml = None
    if payload.engagement_id:
        target_dir = WORKSPACE_DIR / ("retos" if payload.type == "reto" else "engagements") / payload.engagement_id
        target_yaml = target_dir / "target.yaml"

    playbook_data = None
    for p_dir in _get_playbook_dirs(target_dir):
        for f in sorted(p_dir.glob("*.yaml")) + sorted(p_dir.glob("*.yml")):
            if f.is_file():
                try:
                    pb = load_playbook_file(f)
                    if pb.get("id") == playbook_id:
                        playbook_data = pb
                        break
                except Exception:
                    continue
        if playbook_data:
            break

    if not playbook_data:
        raise HTTPException(status_code=404, detail=f"Playbook '{playbook_id}' no encontrado.")

    # Buscar el paso por su id
    step = next((s for s in playbook_data.get("steps", []) if s.get("id") == payload.step_id), None)
    if not step:
        raise HTTPException(status_code=404, detail=f"Paso '{payload.step_id}' no encontrado en playbook '{playbook_id}'.")

    context = {
        "parameters": payload.parameters or {},
    }

    if target_yaml and target_yaml.is_file():
        scope_eval = validate_playbook_against_scope(playbook_data, target_yaml)
        context["allow_passive"] = scope_eval["authorization_state"]["allow_passive"]
        context["allow_active"] = scope_eval["authorization_state"]["allow_active"]
    elif payload.dry_run:
        context["allow_passive"] = True
        context["allow_active"] = True

    try:
        step_result = execute_playbook_step(
            step=step,
            context=context,
            dry_run=payload.dry_run,
        )
        return {
            "playbook_id": playbook_id,
            "step_id": payload.step_id,
            "step_result": step_result,
            "dry_run": payload.dry_run,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al ejecutar el paso: {e}")



