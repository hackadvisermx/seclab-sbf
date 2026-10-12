import datetime
import hashlib
import os
import pathlib
import re
from typing import Any, Dict, List, Optional, Set

from app.services.workspace_sync import workspace_service

KNOWN_TOP_FILES = {
    "target.yaml",
    "target.yml",
    "scope.txt",
    "notes.md",
    "REPORT.md",
    "terminal.log",
}

KNOWN_SUBDIRS = (
    "evidence",
    "recon",
    "loot",
    "fuzzing",
    "screenshots",
    "deliverables",
    "exports",
)

UNCERTAINTY_MARKERS = [
    "posible",
    "podría",
    "podrian",
    "podríamos",
    "candidato",
    "por verificar",
    "sujeto a confirmación",
    "sujeto a revision",
    "requiere validación",
    "requiere confirmación",
    "presunto",
    "no confirmado",
    "estimado",
    "sospecha",
    "hipótesis",
    "potencial",
    "probable",
    "indicio",
    "tentativo",
    "supuesto",
]


class CitationsService:
    """Servicio de detección y verificación de citas a artefactos del proyecto."""

    def extract_file_references(self, text: str) -> List[str]:
        """Extrae referencias textuales a archivos del workspace presentes en el texto."""
        if not text or not isinstance(text, str):
            return []

        candidates: List[str] = []
        seen: Set[str] = set()

        def add_candidate(raw: str):
            if not raw:
                return
            cleaned = raw.strip()
            # Eliminar anclajes (#...) o parámetros (?...)
            cleaned = cleaned.split("#")[0].split("?")[0]
            # Eliminar delimitadores envolventes
            cleaned = cleaned.strip("`\"'()[]<>{}*~")
            # Eliminar puntuación final
            cleaned = re.sub(r"[.,:;!?]+$", "", cleaned).strip()
            if not cleaned:
                return

            # Descartar URLs absolutas externas
            if cleaned.startswith(("http://", "https://", "ftp://", "file://", "//")):
                return

            # Prohibir path traversal y rutas absolutas
            if cleaned.startswith(("/", "\\")) or "\0" in cleaned or ".." in cleaned.split("/"):
                return

            parts = cleaned.split("/")
            first = parts[0]

            is_valid = False
            # Archivos raíz reconocidos
            if len(parts) == 1 and cleaned.lower() in {f.lower() for f in KNOWN_TOP_FILES}:
                # Normalizar mayúsculas de archivos conocidos
                for known in KNOWN_TOP_FILES:
                    if cleaned.lower() == known.lower():
                        cleaned = known
                        break
                is_valid = True
            elif len(parts) >= 2 and first in KNOWN_SUBDIRS:
                # Archivos dentro de subdirectorios del workspace
                is_valid = True

            if is_valid and cleaned not in seen:
                seen.add(cleaned)
                candidates.append(cleaned)

        # 1. Enlaces markdown: [texto](ruta)
        for m in re.finditer(r"\[([^\]]*)\]\(([^)]+)\)", text):
            add_candidate(m.group(2))

        # 2. Código inline con backticks: `ruta`
        for m in re.finditer(r"`([^`\n]+)`", text):
            add_candidate(m.group(1))

        # 3. Referencias de subcarpetas en texto plano: evidence/..., recon/...
        for m in re.finditer(
            r"\b(?:evidence|recon|loot|fuzzing|screenshots|deliverables|exports)/[a-zA-Z0-9_.-]+(?:/[a-zA-Z0-9_.-]+)*\b",
            text,
        ):
            add_candidate(m.group(0))

        # 4. Archivos raíz en texto plano
        for m in re.finditer(
            r"\b(?:target\.ya?ml|scope\.txt|notes\.md|REPORT\.md|terminal\.log)\b",
            text,
            re.IGNORECASE,
        ):
            add_candidate(m.group(0))

        return candidates

    def classify_citation(self, rel_path: str) -> Dict[str, Any]:
        """Clasifica el tipo de cita y determina la sección de destino en la UI."""
        meta: Dict[str, Any] = {"slug": None, "target_section": "artifacts"}

        if rel_path.startswith("evidence/"):
            meta["type"] = "finding"
            meta["target_section"] = "findings"
            slug = rel_path[len("evidence/") :]
            if slug.endswith(".md"):
                slug = slug[:-3]
            meta["slug"] = slug
        elif rel_path.startswith("recon/"):
            meta["type"] = "recon"
            meta["target_section"] = "recon"
        elif rel_path.startswith("loot/"):
            meta["type"] = "loot"
            meta["target_section"] = "loot"
        elif rel_path in ("target.yaml", "target.yml", "scope.txt"):
            meta["type"] = "scope"
            meta["target_section"] = "scope"
        elif rel_path == "notes.md":
            meta["type"] = "notes"
            meta["target_section"] = "notes"
        elif rel_path == "REPORT.md":
            meta["type"] = "report"
            meta["target_section"] = "report"
        elif rel_path.startswith("deliverables/") or rel_path.startswith("exports/"):
            meta["type"] = "deliverable"
            meta["target_section"] = "report"
        else:
            meta["type"] = "file"
            meta["target_section"] = "artifacts"

        return meta

    def detect_uncertainty_language(self, text: str) -> List[str]:
        """Identifica términos de incertidumbre o conjetura en el texto."""
        if not text:
            return []
        lower = text.lower()
        found = [marker for marker in UNCERTAINTY_MARKERS if marker in lower]
        return found

    def verify_citations(
        self, text: str, engagement_id: str, engagement_type: str = "engagement"
    ) -> List[Dict[str, Any]]:
        """Extrae citas de archivos del workspace y verifica su existencia y huella criptográfica."""
        extracted = self.extract_file_references(text)
        results: List[Dict[str, Any]] = []

        target_dir: Optional[pathlib.Path] = None
        try:
            target_dir = workspace_service._resolve_dir(engagement_id, engagement_type)
        except Exception:
            target_dir = None

        workspace_exists = target_dir is not None and target_dir.exists()
        resolved_workspace = target_dir.resolve() if workspace_exists else None

        for path in extracted:
            classification = self.classify_citation(path)
            citation_info: Dict[str, Any] = {
                "path": path,
                "type": classification["type"],
                "target_section": classification["target_section"],
                "slug": classification.get("slug"),
                "exists": False,
                "sha256": None,
                "size": None,
                "modified": None,
            }

            if not workspace_exists or resolved_workspace is None:
                results.append(citation_info)
                continue

            try:
                candidate = target_dir / path
                # Rechazar symlinks estrictamente por seguridad
                if candidate.is_symlink():
                    results.append(citation_info)
                    continue

                resolved_file = candidate.resolve()
                # Verificar que el archivo resuelto permanece dentro del workspace
                if not resolved_file.is_relative_to(resolved_workspace):
                    results.append(citation_info)
                    continue

                if candidate.is_file():
                    stat_info = candidate.stat()
                    citation_info["exists"] = True
                    citation_info["size"] = stat_info.st_size
                    citation_info["modified"] = datetime.datetime.fromtimestamp(
                        stat_info.st_mtime, datetime.timezone.utc
                    ).isoformat()

                    hasher = hashlib.sha256()
                    with open(candidate, "rb") as f:
                        while chunk := f.read(65536):
                            hasher.update(chunk)
                    citation_info["sha256"] = hasher.hexdigest()

            except (OSError, IOError, ValueError):
                # Cualquier fallo de resolución o acceso mantiene exists=False
                citation_info["exists"] = False
                citation_info["sha256"] = None
                citation_info["size"] = None

            results.append(citation_info)

        return results


citations_service = CitationsService()
