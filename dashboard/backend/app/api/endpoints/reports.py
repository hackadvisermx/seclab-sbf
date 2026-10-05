import pathlib
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse, FileResponse
from app.services.workspace_sync import workspace_service
from app.services.runner_service import runner_service

router = APIRouter(prefix="/reports", tags=["Reportes & Exportación"])


@router.post("/{eng_id}/compile")
def compile_report(eng_id: str, type: str = Query("engagement")):
    """Compila el informe de seguridad a partir de target.yaml y evidence/*.md."""
    target_dir = workspace_service._resolve_dir(eng_id, type)
    if not target_dir.exists():
        raise HTTPException(status_code=404, detail="Directorio del engagement no encontrado")
    return runner_service.compile_report(str(target_dir))


@router.get("/{eng_id}/preview")
def preview_report(eng_id: str, type: str = Query("engagement")):
    """Devuelve el contenido del archivo REPORT.md si ya ha sido compilado."""
    report_file = workspace_service._resolve_dir(eng_id, type) / "REPORT.md"
    if not report_file.exists():
        return {"compiled": False, "content": "El informe aún no ha sido compilado. Haz clic en 'Compilar Reporte'."}
    return {"compiled": True, "content": report_file.read_text(encoding="utf-8", errors="ignore")}


@router.post("/{eng_id}/pack")
def pack_engagement(eng_id: str, sanitize: bool = Query(True), type: str = Query("engagement")):
    """Empaqueta y calcula checksums SHA-256 de todas las evidencias y logs."""
    target_dir = workspace_service._resolve_dir(eng_id, type)
    if not target_dir.exists():
        raise HTTPException(status_code=404, detail="Directorio del engagement no encontrado")
    res = runner_service.pack_engagement(str(target_dir), sanitize=sanitize)

    # Identificar el paquete generado en exports/
    exports_dir = target_dir / "exports"
    latest_bundle = None
    if exports_dir.is_dir():
        pkgs = sorted(list(exports_dir.glob("*.tar.gz")) + list(exports_dir.glob("*.zip")), key=lambda p: p.stat().st_mtime, reverse=True)
        if pkgs:
            latest_bundle = pkgs[0].name

    res["latest_bundle"] = latest_bundle
    return res


@router.get("/{eng_id}/download")
def download_engagement(eng_id: str, type: str = Query("engagement")):
    """Descarga el último paquete comprimido .tar.gz generado en exports/."""
    target_dir = workspace_service._resolve_dir(eng_id, type)
    if not target_dir.exists():
        raise HTTPException(status_code=404, detail="Directorio no encontrado")

    exports_dir = target_dir / "exports"
    if not exports_dir.is_dir() or not any(exports_dir.iterdir()):
        # Si no existe, empaquetar automáticamente primero
        runner_service.pack_engagement(str(target_dir), sanitize=True)

    pkgs = sorted(list(exports_dir.glob("*.tar.gz")) + list(exports_dir.glob("*.zip")), key=lambda p: p.stat().st_mtime, reverse=True)
    if not pkgs:
        raise HTTPException(status_code=404, detail="No se encontró ningún paquete para descargar")

    latest_pkg = pkgs[0]
    media_type = "application/gzip" if latest_pkg.name.endswith(".tar.gz") else "application/zip"
    return FileResponse(
        path=str(latest_pkg),
        filename=latest_pkg.name,
        media_type=media_type,
    )
