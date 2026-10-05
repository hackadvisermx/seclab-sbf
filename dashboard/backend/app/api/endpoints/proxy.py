from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from app.models.schemas import ChatCompletionRequest, ChatCompletionResponse
from app.services.proxy_service import proxy_service

router = APIRouter(prefix="/proxy", tags=["SecLab Tactical Proxy Gateway"])


@router.post("/ai/chat", response_model=ChatCompletionResponse)
async def proxy_chat_completion(
    payload: ChatCompletionRequest,
    profile: Optional[str] = Query(None, description="Perfil de inferencia: quick, deep, local"),
):
    """Enruta peticiones de LLM con failover automático utilizando las credenciales seguras del Vault."""
    try:
        return await proxy_service.chat_completion(payload, profile=profile)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error en comunicación upstream: {str(e)}")


@router.get("/recon/shodan/{ip}")
async def proxy_shodan_host(ip: str):
    """Consulta Shodan Host mediante la API key almacenada sin exponerla al cliente."""
    try:
        return await proxy_service.shodan_host_query(ip)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/stats")
def get_proxy_statistics():
    """Retorna métricas de uso acumuladas, latencia y tokens del Tactical Proxy."""
    return proxy_service.get_stats()


@router.get("/history")
def get_proxy_audit_history(limit: int = Query(50, le=200)):
    """Obtiene el historial de auditoría de peticiones despachadas por el Proxy."""
    return proxy_service.get_audit_history(limit=limit)
