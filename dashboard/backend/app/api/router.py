from fastapi import APIRouter, Depends
from app.api.endpoints import (
    auth,
    engagements,
    trash,
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
protected = APIRouter(dependencies=[Depends(auth.require_operator)])
protected.include_router(engagements.router)
protected.include_router(trash.router)
protected.include_router(scope.router)
protected.include_router(findings.router)
protected.include_router(vault.router)
protected.include_router(proxy.router)
protected.include_router(copilot.router)
protected.include_router(logs.router)
protected.include_router(checklist.router)
protected.include_router(reports.router)
protected.include_router(help_center.router)
protected.include_router(system.router)
protected.include_router(loot.router)
protected.include_router(vpn.router)
protected.include_router(recon.router)

api_router.include_router(protected)
