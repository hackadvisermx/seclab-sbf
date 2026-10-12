import pathlib
from typing import Any, Dict
from app.services.workspace_sync import workspace_service
from seclab_metrics import compute_engagement_metrics


class MetricsService:
    def get_metrics(self, eng_id: str, eng_type: str = "engagement") -> Dict[str, Any]:
        """Obtiene las métricas operacionales locales para un engagement o reto."""
        target_dir = workspace_service._resolve_dir(eng_id, eng_type)
        if not target_dir.exists():
            raise FileNotFoundError(f"Engagement {eng_id} no encontrado")
        return compute_engagement_metrics(target_dir)


metrics_service = MetricsService()
