from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Literal
from app.services.recon_service import recon_service

router = APIRouter(prefix="/recon", tags=["Reconocimiento & Scope Guard"])


class ReconRunRequest(BaseModel):
    stage: Literal['all', 'subdomains', 'probe', 'urls', 'patterns'] = "all"
    dry_run: bool = False


@router.get("/{id}/status")
def get_recon_status(id: str, type: str = Query("engagement", pattern="^(engagement|reto)$")):
    """Obtiene el estado actual, métricas de reconocimiento y verificaciones de Scope Guard."""
    status = recon_service.get_status(id, type)
    if "error" in status:
        raise HTTPException(status_code=404, detail=status["error"])
    return status


@router.post("/{id}/run")
def run_recon_pipeline(
    id: str,
    req: ReconRunRequest,
    type: str = Query("engagement", pattern="^(engagement|reto)$"),
):
    """Inicia el pipeline automatizado de reconocimiento con filtrado estricto Scope Guard."""
    res = recon_service.run_pipeline(
        engagement_id=id,
        stage=req.stage,
        dry_run=req.dry_run,
        engagement_type=type,
    )
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error", "Error al iniciar el pipeline"))
    return res


@router.get("/{id}/log")
def get_recon_log(
    id: str,
    lines: int = Query(200, ge=1, le=2000),
    type: str = Query("engagement", pattern="^(engagement|reto)$"),
):
    """Retorna la bitácora de ejecución más reciente del pipeline de reconocimiento."""
    content = recon_service.get_log(id, lines=lines, engagement_type=type)
    return {"engagement_id": id, "lines": lines, "content": content}


@router.post("/{id}/cancel")
def cancel_recon_pipeline(id: str, type: str = Query("engagement", pattern="^(engagement|reto)$")):
    result = recon_service.cancel_pipeline(id, type)
    if not result.get('success'):
        raise HTTPException(status_code=result['code'], detail=result['error'])
    return result
