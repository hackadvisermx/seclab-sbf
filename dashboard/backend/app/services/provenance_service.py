import json
import pathlib
from typing import Any, Dict
from app.services.workspace_sync import workspace_service
from seclab_provenance import (
    build_provenance_graph,
    export_provenance_graph_mermaid,
    export_provenance_graph_markdown,
)


class ProvenanceService:
    def get_provenance_graph(self, eng_id: str, eng_type: str = "engagement") -> Dict[str, Any]:
        """Obtiene el grafo estructurado de procedencia para un engagement o reto."""
        target_dir = workspace_service._resolve_dir(eng_id, eng_type)
        if not target_dir.exists():
            raise FileNotFoundError(f"Engagement {eng_id} no encontrado")
        return build_provenance_graph(target_dir)

    def export_provenance_graph(self, eng_id: str, eng_type: str = "engagement", format: str = "json") -> str:
        """Exporta el grafo de procedencia en JSON, Mermaid o Markdown."""
        target_dir = workspace_service._resolve_dir(eng_id, eng_type)
        if not target_dir.exists():
            raise FileNotFoundError(f"Engagement {eng_id} no encontrado")
        graph = build_provenance_graph(target_dir)
        fmt = (format or "json").lower()
        if fmt == "mermaid":
            return export_provenance_graph_mermaid(graph)
        elif fmt in ("markdown", "md"):
            return export_provenance_graph_markdown(graph)
        else:
            return json.dumps(graph, indent=2, ensure_ascii=False)


provenance_service = ProvenanceService()
