from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from app.models.schemas import EngagementSummary, EngagementCreate
from app.services.workspace_sync import workspace_service
from app.services.recon_service import recon_service

router = APIRouter(prefix="/engagements", tags=["Engagements & Retos"])


@router.get("", response_model=List[EngagementSummary])
def get_engagements():
    """Lista todos los engagements y retos en /workspace."""
    return workspace_service.list_engagements()


@router.post("", response_model=EngagementSummary)
def create_engagement(payload: EngagementCreate):
    """Inicializa un nuevo engagement o reto con target.yaml y plantillas sembradas."""
    try:
        return workspace_service.create_engagement(
            name=payload.name,
            eng_type=payload.type,
            domain=payload.domain,
            client=payload.client,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{eng_id}")
def get_engagement_detail(eng_id: str, type: str = Query("engagement")):
    """Obtiene los detalles, notas y estadísticas del engagement."""
    target_yaml = workspace_service.get_target_yaml(eng_id, type)
    notes = workspace_service.get_notes(eng_id, type)
    findings = workspace_service.list_findings(eng_id, type)
    return {
        "id": eng_id,
        "type": type,
        "target_yaml": target_yaml,
        "notes": notes,
        "findings_count": len(findings),
    }


@router.put("/{eng_id}/notes")
def update_notes(eng_id: str, payload: dict, type: str = Query("engagement")):
    """Actualiza las notas (notes.md) de un engagement."""
    content = payload.get("content", "")
    workspace_service.save_notes(eng_id, content, type)
    return {"status": "ok", "message": "Notas actualizadas exitosamente"}


@router.delete("/{eng_id}")
def delete_engagement(eng_id: str, type: str = Query("engagement")):
    try:
        entry = recon_service.delete_engagement(eng_id, type)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error))
    except OSError:
        raise HTTPException(status_code=500, detail="No se pudo mover el proyecto a la papelera. Revisa los permisos de sus archivos.")
    return {"status": "ok", "id": eng_id, "type": type, "trash_entry": entry}
