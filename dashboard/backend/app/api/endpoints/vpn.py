from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.services.vpn_service import vpn_service

router = APIRouter(prefix="/vpn", tags=["VPN & Conectividad Táctica"])


class VpnActionRequest(BaseModel):
    profile: str
    username: Optional[str] = None
    password: Optional[str] = None
    save_in_vault: Optional[bool] = False


@router.get("/status")
def get_vpn_status():
    """Retorna el estado en tiempo real de la VPN (perfil activo, IP tun0, socket de control)."""
    return vpn_service.get_vpn_status()


@router.get("/saved-credentials")
def list_saved_credentials():
    """Retorna qué perfiles tienen credenciales registradas en el Vault."""
    return vpn_service.list_saved_profiles()


@router.post("/connect")
def connect_vpn(req: VpnActionRequest):
    """Solicita la conexión a un perfil VPN autorizado con o sin credenciales de usuario/contraseña."""
    res = vpn_service.connect(
        profile=req.profile,
        username=req.username,
        password=req.password,
        save_in_vault=bool(req.save_in_vault),
    )
    if not res.get("success") and "no autorizado" in res.get("message", ""):
        raise HTTPException(status_code=400, detail=res["message"])
    return res


@router.post("/disconnect")
def disconnect_vpn():
    """Desconecta la VPN activa y limpia rutas y credenciales efímeras."""
    return vpn_service.disconnect()


@router.post("/switch")
def switch_vpn(req: VpnActionRequest):
    """Conmuta hacia otro perfil VPN autorizado con o sin credenciales."""
    res = vpn_service.switch(
        profile=req.profile,
        username=req.username,
        password=req.password,
        save_in_vault=bool(req.save_in_vault),
    )
    if not res.get("success") and "no autorizado" in res.get("message", ""):
        raise HTTPException(status_code=400, detail=res["message"])
    return res


@router.delete("/saved-credentials/{profile}")
def delete_saved_credentials(profile: str):
    """Elimina las credenciales guardadas de un perfil VPN del Vault."""
    canonical = vpn_service.canonical_profile(profile)
    if not canonical:
        raise HTTPException(status_code=400, detail=f"Perfil '{profile}' no autorizado.")
    success = vpn_service.delete_saved_credentials(canonical)
    return {"status": "ok", "deleted": success, "profile": canonical}
