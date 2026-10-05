from typing import Any, Dict
from fastapi import APIRouter, HTTPException, Query
from app.models.schemas import ScopeCheckRequest, ScopeCheckResponse
from app.services.workspace_sync import workspace_service
from app.services.runner_service import runner_service

router = APIRouter(prefix="/scope", tags=["Alcance & Scope Guard"])


@router.get("/{eng_id}")
def get_scope_config(eng_id: str, type: str = Query("engagement")):
    """Obtiene la configuración de alcance desde target.yaml."""
    data = workspace_service.get_target_yaml(eng_id, type)
    if not data:
        raise HTTPException(status_code=404, detail="target.yaml no encontrado para este engagement")
    return data


@router.put("/{eng_id}")
def update_scope_config(eng_id: str, payload: Dict[str, Any], type: str = Query("engagement")):
    """Actualiza la configuración de alcance en target.yaml."""
    success = workspace_service.save_target_yaml(eng_id, payload, type)
    if not success:
        raise HTTPException(status_code=500, detail="Error al guardar target.yaml")
    return {"status": "ok", "message": "target.yaml guardado con éxito"}


@router.post("/check", response_model=ScopeCheckResponse)
def check_target_scope(payload: ScopeCheckRequest, type: str = Query("engagement")):
    """Verifica en tiempo real si un objetivo está dentro del alcance o expresamente excluido."""
    if not payload.engagement_id:
        raise HTTPException(status_code=400, detail="Debes indicar engagement_id para verificar el alcance")

    target_dir = workspace_service._resolve_dir(payload.engagement_id, type)
    yaml_path = target_dir / "target.yaml"
    if not yaml_path.exists():
        raise HTTPException(status_code=404, detail=f"target.yaml no encontrado en {target_dir}")

    return runner_service.check_scope(payload.target, str(yaml_path))
