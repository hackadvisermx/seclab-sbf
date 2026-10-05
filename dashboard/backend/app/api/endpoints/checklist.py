from fastapi import APIRouter, HTTPException, Query
from app.services.workspace_sync import workspace_service
from app.services.runner_service import runner_service

router = APIRouter(prefix="/checklist", tags=["Metodología & Cobertura"])


@router.get("/{eng_id}")
def get_engagement_checklist(eng_id: str, type: str = Query("engagement")):
    """Calcula la cobertura metodológica contra las 8 disciplinas mediante pt-audit-checklist."""
    target_dir = workspace_service._resolve_dir(eng_id, type)
    if not target_dir.exists():
        raise HTTPException(status_code=404, detail="Directorio del engagement no encontrado")
    return runner_service.get_audit_checklist(str(target_dir))


@router.get("/{eng_id}/next")
def get_engagement_next_step(eng_id: str, prompt: bool = Query(False), type: str = Query("engagement")):
    """Obtiene la recomendación inteligente de próximo paso táctico o prompt para agentes con pt-next."""
    target_dir = workspace_service._resolve_dir(eng_id, type)
    if not target_dir.exists():
        raise HTTPException(status_code=404, detail="Directorio del engagement no encontrado")
    return runner_service.get_audit_next_step(str(target_dir), prompt_mode=prompt)
