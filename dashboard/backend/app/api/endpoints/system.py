from fastapi import APIRouter
from app.services.telemetry import telemetry_service

router = APIRouter(prefix="/system", tags=["Telemetría & Estado del Laboratorio"])


@router.get("/telemetry")
def get_telemetry():
    """Retorna métricas de red, interfaces (tun0, tailscale), disco y sesiones tmux."""
    return telemetry_service.get_system_telemetry()


@router.get("/info")
def get_system_info():
    """Identidad y versión del entorno SecLab-SBF."""
    return {
        "project": "SecLab-SBF",
        "tagline": "Estación de Trabajo Ofensiva y Auditoría Táctica",
        "user": "tester",
        "default_shell": "zsh",
        "evidence_standard": "Evidence-First",
        "version": "1.0.0-tactical",
    }
