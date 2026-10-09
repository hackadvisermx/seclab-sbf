from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from app.services.workspace_sync import workspace_service
from app.core.artifact_snapshot import ArtifactChangedError

router = APIRouter(prefix="/loot", tags=["Botín, Banderas & Artefactos"])


@router.get("/{eng_id}")
def get_engagement_loot(eng_id: str, type: str = Query("engagement")):
    """Devuelve las credenciales capturadas y los archivos en la carpeta loot/."""
    return workspace_service.get_loot(eng_id, type)


@router.post("/{eng_id}/credentials")
def save_credential(eng_id: str, payload: Dict[str, Any], type: str = Query("engagement")):
    """Guarda o actualiza una credencial (usuario, contraseña/hash, servicio) en loot/credentials.json."""
    if not payload.get("username") and not payload.get("password") and not payload.get("hash"):
        raise HTTPException(status_code=400, detail="Debe proveer al menos un nombre de usuario, contraseña o hash")
    return workspace_service.save_loot_credential(eng_id, payload, type)


@router.delete("/{eng_id}/credentials/{cred_id}")
def delete_credential(eng_id: str, cred_id: str, type: str = Query("engagement")):
    """Elimina una credencial de loot/credentials.json."""
    deleted = workspace_service.delete_loot_credential(eng_id, cred_id, type)
    if not deleted:
        raise HTTPException(status_code=404, detail="Credencial no encontrada")
    return {"status": "ok", "message": "Credencial eliminada exitosamente"}


@router.get("/{eng_id}/flags")
def get_ctf_flags(eng_id: str, type: str = Query("reto")):
    """Obtiene las banderas capturadas (user, root, custom) de un reto CTF."""
    return workspace_service.get_flags(eng_id, type)


@router.post("/{eng_id}/flags")
def save_ctf_flags(eng_id: str, payload: Dict[str, Any], type: str = Query("reto")):
    """Actualiza el estado de las banderas capturadas."""
    return workspace_service.save_flags(eng_id, payload, type)


@router.get("/{eng_id}/artifacts")
def list_artifacts(eng_id: str, folder: str = Query("recon"), type: str = Query("engagement")):
    """Lista archivos generados en recon/, fuzzing/, loot/, screenshots/ o exports/."""
    return workspace_service.list_artifacts(eng_id, folder, type)


@router.get("/{eng_id}/artifacts/content")
def get_artifact_content(eng_id: str, path: str = Query(...), type: str = Query("engagement")):
    """Lee el contenido textual de un artefacto generado."""
    try:
        return workspace_service.get_artifact_content(eng_id, path, type)
    except ArtifactChangedError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
