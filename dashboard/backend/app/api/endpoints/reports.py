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

    archive_path = res.get("archive_path")
    res["latest_bundle"] = pathlib.Path(archive_path).name if res.get("success") and archive_path else None
    return res


@router.get("/{eng_id}/download")
def download_engagement(eng_id: str, type: str = Query("engagement")):
    """Descarga el último paquete comprimido .tar.gz generado en exports/."""
    target_dir = workspace_service._resolve_dir(eng_id, type)
    if not target_dir.exists():
        raise HTTPException(status_code=404, detail="Directorio no encontrado")

    result = runner_service.pack_engagement(str(target_dir), sanitize=True)
    if not result.get("success"):
        raise HTTPException(status_code=409, detail=result.get("stderr") or result.get("stdout") or "Exportación bloqueada; revisa alcance y evidencias.")
    archive_path = result.get("archive_path")
    if not archive_path:
        raise HTTPException(status_code=500, detail="El empaquetador no devolvió un archivo generado.")
    latest_pkg = pathlib.Path(archive_path).resolve()
    exports_dir = (target_dir / "exports").resolve()
    if latest_pkg.parent != exports_dir or not latest_pkg.is_file():
        raise HTTPException(status_code=500, detail="El paquete generado no está disponible en exports/.")
    media_type = "application/gzip" if latest_pkg.name.endswith(".tar.gz") else "application/zip"
    return FileResponse(
        path=str(latest_pkg),
        filename=latest_pkg.name,
        media_type=media_type,
    )
