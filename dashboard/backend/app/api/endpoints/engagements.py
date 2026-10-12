from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Response
from app.models.schemas import EngagementSummary, EngagementCreate, EngagementTimelineResponse
from app.services.workspace_sync import workspace_service
from app.services.recon_service import recon_service
from app.services.timeline_service import timeline_service
from app.services.supervision_service import supervision_service
from app.services.metrics_service import metrics_service

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
            subtype=payload.subtype,
            category=payload.category,
            points=payload.points,
            difficulty=payload.difficulty,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{eng_id}")
def get_engagement_detail(eng_id: str, type: str = Query("engagement")):
    """Obtiene los detalles, notas y estadísticas del engagement."""
    target_yaml = workspace_service.get_target_yaml(eng_id, type)
    notes = workspace_service.get_notes(eng_id, type)
    findings = workspace_service.list_findings(eng_id, type)
    flags = workspace_service.get_flags(eng_id, type) if type == "reto" else {}
    eng_meta = (target_yaml.get("engagement") or {}) if isinstance(target_yaml, dict) else {}
    return {
        "id": eng_id,
        "type": type,
        "subtype": flags.get("subtype") or eng_meta.get("subtype", "machine" if type == "reto" else None),
        "category": flags.get("category") or eng_meta.get("category"),
        "points": flags.get("points") if flags.get("points") is not None else eng_meta.get("points"),
        "difficulty": flags.get("difficulty") or eng_meta.get("difficulty"),
        "is_solved": bool(flags.get("solved")),
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


@router.get("/{eng_id}/timeline", response_model=EngagementTimelineResponse)
def get_engagement_timeline(eng_id: str, type: str = Query("engagement")):
    """Obtiene la línea de tiempo unificada cronológica del engagement."""
    return timeline_service.get_timeline(eng_id, type)


@router.get("/{eng_id}/timeline/export")
def export_engagement_timeline(
    eng_id: str,
    type: str = Query("engagement"),
    format: str = Query("json", pattern="^(json|markdown|md)$"),
):
    """Exporta la línea de tiempo unificada cronológica en formato JSON o Markdown."""
    try:
        content = timeline_service.export_timeline(eng_id, type, format)
        media_type = "application/json" if format == "json" else "text/markdown; charset=utf-8"
        ext = "json" if format == "json" else "md"
        return Response(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="timeline_{eng_id}.{ext}"'},
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{eng_id}/supervision")
def get_engagement_supervision(eng_id: str, type: str = Query("engagement")):
    """Obtiene el estado de supervisión consolidado y checkpoints pedagógicos de auditoría."""
    try:
        return supervision_service.get_supervision_state(eng_id, type)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{eng_id}/supervision/export")
def export_engagement_supervision(
    eng_id: str,
    type: str = Query("engagement"),
    format: str = Query("json", pattern="^(json|markdown|md)$"),
):
    """Exporta el informe consolidado de supervisión pedagógica en formato JSON o Markdown."""
    try:
        content = supervision_service.export_supervision_report(eng_id, type, format)
        media_type = "application/json" if format == "json" else "text/markdown; charset=utf-8"
        ext = "json" if format == "json" else "md"
        return Response(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="supervision_{eng_id}.{ext}"'},
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/{eng_id}/metrics")
def get_engagement_metrics(eng_id: str, type: str = Query("engagement")):
    """Obtiene las métricas operacionales locales y avance de calidad de la auditoría."""
    try:
        return metrics_service.get_metrics(eng_id, type)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))



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
