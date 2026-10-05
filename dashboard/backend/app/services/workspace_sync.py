import datetime
import json
import os
import pathlib
import re
import yaml
from typing import Any, Dict, List, Optional, Tuple
from app.config import WORKSPACE_DIR, TEMPLATES_DIR, SCRIPTS_DIR
from app.models.schemas import (
    EngagementSummary,
    FindingDetail,
    FindingFrontmatter,
    FindingCreate,
)


def _parse_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
    """Extrae metadatos YAML frontmatter y cuerpo markdown."""
    frontmatter = {}
    body = content
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            try:
                frontmatter = yaml.safe_load(parts[1]) or {}
            except Exception:
                pass
            body = parts[2].strip()
    return frontmatter, body


class WorkspaceSyncService:
    def __init__(self, workspace_path: pathlib.Path = WORKSPACE_DIR):
        self.ws_path = workspace_path
        self.ws_path.mkdir(parents=True, exist_ok=True)
        (self.ws_path / "engagements").mkdir(exist_ok=True)
        (self.ws_path / "retos").mkdir(exist_ok=True)

    def _resolve_dir(self, eng_id: str, eng_type: str = "engagement") -> pathlib.Path:
        sub_dir = "retos" if eng_type in ("reto", "retos") else "engagements"
        return self.ws_path / sub_dir / eng_id

    def list_engagements(self) -> List[EngagementSummary]:
        """Escanea el workspace y lista todos los engagements y retos registrados."""
        results = []
        for cat in ("engagements", "retos"):
            cat_dir = self.ws_path / cat
            if not cat_dir.exists():
                continue
            for item in sorted(cat_dir.iterdir()):
                if not item.is_dir() or item.name.startswith((".", "_")):
                    continue

                eng_id = item.name
                eng_type = "reto" if cat == "retos" else "engagement"
                target_yaml_path = item / "target.yaml"
                notes_path = item / "notes.md"
                evidence_dir = item / "evidence"
                log_path = item / "terminal.log"

                # Conteo de evidencias
                ev_count = 0
                if evidence_dir.exists():
                    ev_count = len([f for f in evidence_dir.glob("*.md") if f.is_file()])

                # Líneas de log
                log_lines = 0
                if log_path.exists():
                    try:
                        with open(log_path, "r", errors="ignore") as lf:
                            log_lines = sum(1 for _ in lf)
                    except Exception:
                        pass

                # Metadatos desde target.yaml si existe
                created_at = None
                client_name = None
                if target_yaml_path.exists():
                    try:
                        with open(target_yaml_path, "r") as yf:
                            ydata = yaml.safe_load(yf) or {}
                            eng_meta = ydata.get("engagement", {})
                            created_at = eng_meta.get("created_at")
                            client_name = eng_meta.get("client")
                    except Exception:
                        pass

                results.append(
                    EngagementSummary(
                        id=eng_id,
                        name=eng_id,
                        type=eng_type,
                        path=str(item),
                        created_at=created_at or datetime.date.today().isoformat(),
                        client_or_platform=client_name or ("Plataforma CTF" if eng_type == "reto" else "Cliente"),
                        has_target_yaml=target_yaml_path.exists(),
                        has_notes=notes_path.exists(),
                        evidence_count=ev_count,
                        terminal_log_lines=log_lines,
                        favorite=False,
                        archived=False,
                    )
                )
        return results

    def create_engagement(
        self,
        name: str,
        eng_type: str = "engagement",
        domain: Optional[str] = None,
        client: Optional[str] = None,
    ) -> EngagementSummary:
        """Crea la estructura de carpetas y siembra target.yaml, scope.txt y notes.md."""
        clean_name = re.sub(r"[^a-zA-Z0-9._-]", "", name)
        target_dir = self._resolve_dir(clean_name, eng_type)
        target_dir.mkdir(parents=True, exist_ok=True)

        for folder in ("recon", "fuzzing", "evidence", "loot", "screenshots"):
            (target_dir / folder).mkdir(exist_ok=True)

        # Sembrar target.yaml
        now_date = datetime.date.today().isoformat()
        sample_domain = domain or f"{clean_name}.local"
        sample_client = client or ("Plataforma CTF" if eng_type == "reto" else clean_name.capitalize())

        target_yaml_data = {
            "version": "1.0",
            "engagement": {
                "name": clean_name,
                "type": eng_type,
                "created_at": now_date,
                "auditor": "tester",
                "client": sample_client,
                "tos_reference": "Autorización expresa / Reglas de Laboratorio",
                "emergency_contact": "security@local.internal",
            },
            "network": {
                "vpn_profile": "none",
                "assigned_ip": "",
                "gateway_dns": "",
            },
            "scope": {
                "in_scope": {
                    "domains": [sample_domain, f"*.{sample_domain}"],
                    "ips": [],
                    "cidrs": [],
                    "endpoints": [f"https://{sample_domain}/api"],
                },
                "out_of_scope": {
                    "domains": [f"status.{sample_domain}"],
                    "ips": [],
                    "cidrs": [],
                    "notes": ["Sistemas de terceros y pasarelas fuera de alcance"],
                },
            },
            "operational_limits": {
                "max_requests_per_second": 20,
                "max_parallel_threads": 5,
                "dos_testing": False,
                "social_engineering": False,
                "brute_force_account_lockout_safe": True,
            },
            "reporting": {
                "cvss_version": "3.1",
                "format": "markdown",
                "language": "es",
            },
        }

        with open(target_dir / "target.yaml", "w", encoding="utf-8") as f:
            yaml.dump(target_yaml_data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

        # Sembrar notes.md
        notes_content = f"# Bitácora de Auditoría: {clean_name}\n\n- Fecha: {now_date}\n- Objetivo: {sample_domain}\n\n## Objetivos y Tácticas\n- [ ] Reconocimiento inicial\n- [ ] Identificación de endpoints y servicios\n- [ ] Análisis de vulnerabilidades y matriz de autorización\n"
        with open(target_dir / "notes.md", "w", encoding="utf-8") as f:
            f.write(notes_content)

        return EngagementSummary(
            id=clean_name,
            name=clean_name,
            type=eng_type,
            path=str(target_dir),
            created_at=now_date,
            client_or_platform=sample_client,
            has_target_yaml=True,
            has_notes=True,
            evidence_count=0,
            terminal_log_lines=0,
        )

    def get_target_yaml(self, eng_id: str, eng_type: str = "engagement") -> Dict[str, Any]:
        """Lee y devuelve el contenido estructurado de target.yaml."""
        target_file = self._resolve_dir(eng_id, eng_type) / "target.yaml"
        if not target_file.exists():
            return {}
        with open(target_file, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def save_target_yaml(self, eng_id: str, data: Dict[str, Any], eng_type: str = "engagement") -> bool:
        """Guarda la especificación de alcance en target.yaml."""
        target_file = self._resolve_dir(eng_id, eng_type) / "target.yaml"
        target_file.parent.mkdir(parents=True, exist_ok=True)
        with open(target_file, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        return True

    def list_findings(self, eng_id: str, eng_type: str = "engagement") -> List[FindingDetail]:
        """Obtiene todas las fichas de hallazgos en evidence/*.md."""
        ev_dir = self._resolve_dir(eng_id, eng_type) / "evidence"
        if not ev_dir.exists():
            return []

        findings = []
        for file_path in sorted(ev_dir.glob("*.md")):
            if not file_path.is_file():
                continue
            slug = file_path.stem
            try:
                content = file_path.read_text(encoding="utf-8")
                fm_data, body = _parse_frontmatter(content)
                fm = FindingFrontmatter(
                    title=fm_data.get("title", slug.replace("-", " ").capitalize()),
                    severity=str(fm_data.get("severity", "MEDIUM")).upper(),
                    cvss_score=float(fm_data.get("cvss_score")) if fm_data.get("cvss_score") is not None else None,
                    cvss_vector=fm_data.get("cvss_vector"),
                    cwe=fm_data.get("cwe"),
                    owasp=fm_data.get("owasp"),
                    asset=fm_data.get("asset"),
                    date=str(fm_data.get("date", datetime.date.today().isoformat())),
                    author=fm_data.get("author", "tester"),
                    status=fm_data.get("status", "VERIFIED"),
                )
                findings.append(
                    FindingDetail(
                        slug=slug,
                        filename=file_path.name,
                        frontmatter=fm,
                        body=body,
                        engagement_id=eng_id,
                    )
                )
            except Exception:
                continue
        return findings

    def get_finding(self, eng_id: str, slug: str, eng_type: str = "engagement") -> Optional[FindingDetail]:
        """Retorna el detalle completo de un hallazgo."""
        file_path = self._resolve_dir(eng_id, eng_type) / "evidence" / f"{slug}.md"
        if not file_path.exists():
            return None
        content = file_path.read_text(encoding="utf-8")
        fm_data, body = _parse_frontmatter(content)
        fm = FindingFrontmatter(
            title=fm_data.get("title", slug.replace("-", " ").capitalize()),
            severity=str(fm_data.get("severity", "MEDIUM")).upper(),
            cvss_score=float(fm_data.get("cvss_score")) if fm_data.get("cvss_score") is not None else None,
            cvss_vector=fm_data.get("cvss_vector"),
            cwe=fm_data.get("cwe"),
            owasp=fm_data.get("owasp"),
            asset=fm_data.get("asset"),
            date=str(fm_data.get("date", datetime.date.today().isoformat())),
            author=fm_data.get("author", "tester"),
            status=fm_data.get("status", "VERIFIED"),
        )
        return FindingDetail(
            slug=slug,
            filename=file_path.name,
            frontmatter=fm,
            body=body,
            engagement_id=eng_id,
        )

    def save_finding(self, eng_id: str, finding_create: FindingCreate, eng_type: str = "engagement") -> FindingDetail:
        """Crea o actualiza una ficha en evidence/<slug>.md preservando el formato Evidence-First."""
        ev_dir = self._resolve_dir(eng_id, eng_type) / "evidence"
        ev_dir.mkdir(parents=True, exist_ok=True)
        file_path = ev_dir / f"{finding_create.slug}.md"

        now_date = datetime.date.today().isoformat()
        fm = {
            "title": finding_create.title,
            "severity": finding_create.severity.upper(),
            "cvss_score": finding_create.cvss_score or 5.0,
            "cvss_vector": finding_create.cvss_vector or "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:L/A:N",
            "cwe": finding_create.cwe or "CWE-200",
            "asset": finding_create.asset or "",
            "date": now_date,
            "author": "tester",
            "status": "VERIFIED",
        }

        body_parts = []
        body_parts.append(f"## Descripción\n{finding_create.description or 'Detalles de la vulnerabilidad.'}\n")
        body_parts.append(f"## Pasos para Reproducir\n{finding_create.steps_to_reproduce or '1. Petición inicial\n2. Manipulación de parámetro\n3. Verificación de respuesta'}\n")

        if finding_create.http_request or finding_create.http_response:
            body_parts.append("## Evidencia Técnica (HTTP)")
            if finding_create.http_request:
                body_parts.append(f"```http\n{finding_create.http_request.strip()}\n```")
            if finding_create.http_response:
                body_parts.append(f"```http\n{finding_create.http_response.strip()}\n```")
            body_parts.append("")

        body_parts.append(f"## Remediación y Mitigación\n{finding_create.remediation or 'Implementar validación estricta de entradas y principio de mínimo privilegio.'}\n")

        markdown_body = "\n".join(body_parts)
        file_content = f"---\n{yaml.dump(fm, default_flow_style=False, sort_keys=False, allow_unicode=True)}---\n\n{markdown_body}"

        file_path.write_text(file_content, encoding="utf-8")

        return FindingDetail(
            slug=finding_create.slug,
            filename=file_path.name,
            frontmatter=FindingFrontmatter(**fm),
            body=markdown_body,
            engagement_id=eng_id,
        )

    def delete_finding(self, eng_id: str, slug: str, eng_type: str = "engagement") -> bool:
        """Elimina una ficha de hallazgo."""
        file_path = self._resolve_dir(eng_id, eng_type) / "evidence" / f"{slug}.md"
        if file_path.exists():
            file_path.unlink()
            return True
        return False

    def get_terminal_log(self, eng_id: str, lines: int = 500, eng_type: str = "engagement") -> str:
        """Lee las últimas N líneas del archivo terminal.log."""
        log_file = self._resolve_dir(eng_id, eng_type) / "terminal.log"
        if not log_file.exists():
            return "No se ha iniciado registro de terminal (terminal.log no existe aún para este engagement)."
        try:
            with open(log_file, "r", errors="ignore") as f:
                all_lines = f.readlines()
                return "".join(all_lines[-lines:])
        except Exception as e:
            return f"Error al leer terminal.log: {str(e)}"

    def get_notes(self, eng_id: str, eng_type: str = "engagement") -> str:
        """Lee el archivo notes.md."""
        notes_file = self._resolve_dir(eng_id, eng_type) / "notes.md"
        if not notes_file.exists():
            return ""
        return notes_file.read_text(encoding="utf-8", errors="ignore")

    def save_notes(self, eng_id: str, content: str, eng_type: str = "engagement") -> bool:
        """Guarda notas en notes.md."""
        notes_file = self._resolve_dir(eng_id, eng_type) / "notes.md"
        notes_file.parent.mkdir(parents=True, exist_ok=True)
        notes_file.write_text(content, encoding="utf-8")
        return True

    def get_loot(self, eng_id: str, eng_type: str = "engagement") -> Dict[str, Any]:
        """Obtiene credenciales estructuradas y lista de archivos de botín en loot/."""
        loot_dir = self._resolve_dir(eng_id, eng_type) / "loot"
        loot_dir.mkdir(parents=True, exist_ok=True)

        creds_file = loot_dir / "credentials.json"
        credentials = []
        if creds_file.exists():
            try:
                with open(creds_file, "r", encoding="utf-8") as f:
                    credentials = json.load(f)
            except Exception:
                credentials = []

        files = []
        for f in sorted(loot_dir.iterdir()):
            if f.is_file() and f.name != "credentials.json" and not f.name.startswith("."):
                files.append({
                    "name": f.name,
                    "size": f.stat().st_size,
                    "modified": datetime.datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
                })

        return {"credentials": credentials, "files": files}

    def save_loot_credential(self, eng_id: str, cred: dict, eng_type: str = "engagement") -> dict:
        """Guarda o actualiza una credencial en loot/credentials.json."""
        loot_dir = self._resolve_dir(eng_id, eng_type) / "loot"
        loot_dir.mkdir(parents=True, exist_ok=True)
        creds_file = loot_dir / "credentials.json"

        credentials = []
        if creds_file.exists():
            try:
                with open(creds_file, "r", encoding="utf-8") as f:
                    credentials = json.load(f)
            except Exception:
                credentials = []

        cred_id = cred.get("id") or f"cred-{int(datetime.datetime.now().timestamp())}"
        cred["id"] = cred_id
        cred["captured_at"] = cred.get("captured_at") or datetime.date.today().isoformat()

        updated = False
        for idx, c in enumerate(credentials):
            if c.get("id") == cred_id:
                credentials[idx] = cred
                updated = True
                break
        if not updated:
            credentials.append(cred)

        with open(creds_file, "w", encoding="utf-8") as f:
            json.dump(credentials, f, indent=2, ensure_ascii=False)

        return cred

    def delete_loot_credential(self, eng_id: str, cred_id: str, eng_type: str = "engagement") -> bool:
        """Elimina una credencial de loot/credentials.json."""
        loot_dir = self._resolve_dir(eng_id, eng_type) / "loot"
        creds_file = loot_dir / "credentials.json"
        if not creds_file.exists():
            return False

        try:
            with open(creds_file, "r", encoding="utf-8") as f:
                credentials = json.load(f)
            new_creds = [c for c in credentials if c.get("id") != cred_id]
            with open(creds_file, "w", encoding="utf-8") as f:
                json.dump(new_creds, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False

    def get_flags(self, eng_id: str, eng_type: str = "reto") -> Dict[str, Any]:
        """Obtiene las banderas capturadas de un reto CTF."""
        target_dir = self._resolve_dir(eng_id, eng_type)
        flags_file = target_dir / "flags.json"
        if flags_file.exists():
            try:
                with open(flags_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass

        return {
            "user_flag": {"value": "", "status": "pending", "captured_at": None, "hash": ""},
            "root_flag": {"value": "", "status": "pending", "captured_at": None, "hash": ""},
            "custom_flags": [],
        }

    def save_flags(self, eng_id: str, flags_data: dict, eng_type: str = "reto") -> dict:
        """Guarda el estado de banderas en flags.json."""
        target_dir = self._resolve_dir(eng_id, eng_type)
        target_dir.mkdir(parents=True, exist_ok=True)
        flags_file = target_dir / "flags.json"

        now_iso = datetime.datetime.now().isoformat()
        if flags_data.get("user_flag", {}).get("value") and flags_data["user_flag"].get("status") == "captured":
            if not flags_data["user_flag"].get("captured_at"):
                flags_data["user_flag"]["captured_at"] = now_iso
        if flags_data.get("root_flag", {}).get("value") and flags_data["root_flag"].get("status") == "captured":
            if not flags_data["root_flag"].get("captured_at"):
                flags_data["root_flag"]["captured_at"] = now_iso

        with open(flags_file, "w", encoding="utf-8") as f:
            json.dump(flags_data, f, indent=2, ensure_ascii=False)

        return flags_data

    def list_artifacts(self, eng_id: str, folder: str = "recon", eng_type: str = "engagement") -> List[Dict[str, Any]]:
        """Lista archivos generados en una subcarpeta (recon, fuzzing, loot, screenshots)."""
        target_dir = self._resolve_dir(eng_id, eng_type)
        allowed_folders = {"recon", "fuzzing", "loot", "screenshots", "exports", "evidence"}
        if folder not in allowed_folders:
            folder = "recon"

        sub_dir = target_dir / folder
        if not sub_dir.exists():
            return []

        results = []
        for p in sorted(sub_dir.iterdir()):
            if p.is_file() and not p.name.startswith("."):
                results.append({
                    "name": p.name,
                    "folder": folder,
                    "rel_path": f"{folder}/{p.name}",
                    "size": p.stat().st_size,
                    "modified": datetime.datetime.fromtimestamp(p.stat().st_mtime).isoformat(),
                    "is_text": p.suffix.lower() in {".txt", ".json", ".md", ".csv", ".yaml", ".yml", ".html", ".log", ".xml"},
                    "is_image": p.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"},
                })
        return results

    def get_artifact_content(self, eng_id: str, rel_path: str, eng_type: str = "engagement") -> Dict[str, Any]:
        """Lee el contenido de un archivo de artefacto de forma segura contra path traversal."""
        target_dir = self._resolve_dir(eng_id, eng_type).resolve()
        requested_path = (target_dir / rel_path).resolve()

        if not str(requested_path).startswith(str(target_dir)) or not requested_path.is_file():
            raise FileNotFoundError("Archivo de artefacto no encontrado o acceso denegado")

        size = requested_path.stat().st_size
        if size > 2 * 1024 * 1024:
            content = f"[Archivo demasiado grande para previsualizar: {size} bytes]"
        else:
            try:
                content = requested_path.read_text(encoding="utf-8", errors="replace")
            except Exception as e:
                content = f"[No se pudo decodificar archivo de texto: {str(e)}]"

        return {
            "name": requested_path.name,
            "rel_path": rel_path,
            "size": size,
            "content": content,
        }


workspace_service = WorkspaceSyncService()
