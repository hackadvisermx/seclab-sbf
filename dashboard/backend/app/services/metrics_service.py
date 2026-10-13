import pathlib
from typing import Any, Dict
from app.services.workspace_sync import workspace_service
from seclab_metrics import (
    compute_engagement_metrics,
    export_metrics_report,
    compute_cross_engagement_summary,
    record_metrics_snapshot,
    get_metrics_history,
)


class MetricsService:
    def get_metrics(self, eng_id: str, eng_type: str = "engagement") -> Dict[str, Any]:
        """Obtiene las métricas operacionales locales para un engagement o reto."""
        target_dir = workspace_service._resolve_dir(eng_id, eng_type)
        if not target_dir.exists():
            raise FileNotFoundError(f"Engagement {eng_id} no encontrado")
        return compute_engagement_metrics(target_dir)

    def record_snapshot(self, eng_id: str, eng_type: str = "engagement", author: str = "tester") -> Dict[str, Any]:
        """Captura y persiste una instantánea de métricas en evidence/.metrics_history.jsonl (V3-07e)."""
        target_dir = workspace_service._resolve_dir(eng_id, eng_type)
        if not target_dir.exists():
            raise FileNotFoundError(f"Engagement {eng_id} no encontrado")
        return record_metrics_snapshot(target_dir, author=author)

    def get_history(self, eng_id: str, eng_type: str = "engagement") -> list:
        """Devuelve el historial cronológico inverso de capturas de métricas."""
        target_dir = workspace_service._resolve_dir(eng_id, eng_type)
        if not target_dir.exists():
            raise FileNotFoundError(f"Engagement {eng_id} no encontrado")
        return get_metrics_history(target_dir)

    def export_metrics_report(self, eng_id: str, eng_type: str = "engagement", format: str = "json") -> str:
        """Exporta el informe consolidado de métricas operacionales en formato JSON o Markdown."""
        target_dir = workspace_service._resolve_dir(eng_id, eng_type)
        if not target_dir.exists():
            raise FileNotFoundError(f"Engagement {eng_id} no encontrado")
        return export_metrics_report(target_dir, format=format)

    def get_cross_engagement_summary(self) -> Dict[str, Any]:
        """Calcula el resumen consolidado de métricas operacionales a través de todo el workspace."""
        return compute_cross_engagement_summary(workspace_service.ws_path)


metrics_service = MetricsService()

