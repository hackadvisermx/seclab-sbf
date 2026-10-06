from typing import List
from fastapi import APIRouter, HTTPException
from app.models.schemas import ApiKeyCreate, ApiKeyResponse, ApiKeyUpdate, HealthCheckResult, ModelCatalogRequest
from app.services.vault_service import vault_service

router = APIRouter(prefix="/vault", tags=["Hermes API Key Vault"])


@router.get("", response_model=List[ApiKeyResponse])
def get_vault_keys():
    """Lista todas las API keys configuradas con valores enmascarados y estados de salud."""
    return vault_service.list_keys()


@router.post("", response_model=ApiKeyResponse)
def upsert_vault_key(payload: ApiKeyCreate):
    """Guarda o actualiza una API key cifrada con AES-256-GCM en el Vault."""
    try:
        return vault_service.upsert_key(payload)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/models/preview")
async def preview_models(payload: ModelCatalogRequest):
    try:
        return await vault_service.list_models(payload.provider, payload.api_key, payload.base_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/{provider}/models")
async def provider_models(provider: str):
    return await preview_models(ModelCatalogRequest(provider=provider))


@router.put("/{provider}", response_model=ApiKeyResponse)
def update_vault_key(provider: str, payload: ApiKeyUpdate):
    """Actualiza una clave o parámetros de endpoint existentes."""
    res = vault_service.update_key(provider, payload)
    if not res:
        raise HTTPException(status_code=404, detail=f"Proveedor '{provider}' no encontrado en el Vault")
    return res


@router.delete("/{provider}")
def delete_vault_key(provider: str):
    """Elimina una API key del Vault."""
    success = vault_service.delete_key(provider)
    if not success:
        raise HTTPException(status_code=404, detail="Clave no encontrada")
    return {"status": "ok", "message": f"Clave para {provider} eliminada con éxito"}


@router.post("/{provider}/test", response_model=HealthCheckResult)
async def test_key_health(provider: str):
    """Prueba la conectividad y validez de la API key contra su servicio upstream."""
    return await vault_service.check_health(provider)
