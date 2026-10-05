from fastapi import APIRouter
from app.api.endpoints import (
    auth,
    engagements,
    scope,
    findings,
    vault,
    proxy,
    logs,
    checklist,
    reports,
    help_center,
    system,
    copilot,
    loot,
    vpn,
    recon,
)

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(engagements.router)
api_router.include_router(scope.router)
api_router.include_router(findings.router)
api_router.include_router(vault.router)
api_router.include_router(proxy.router)
api_router.include_router(copilot.router)
api_router.include_router(logs.router)
api_router.include_router(checklist.router)
api_router.include_router(reports.router)
api_router.include_router(help_center.router)
api_router.include_router(system.router)
api_router.include_router(loot.router)
api_router.include_router(vpn.router)
api_router.include_router(recon.router)
