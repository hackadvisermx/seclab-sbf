import datetime
import json
import pathlib
import re
import sys
import uuid
import yaml
from typing import Any, Dict, List, Optional, Tuple
from app.config import WORKSPACE_DIR, TEMPLATES_DIR, SCRIPTS_DIR
from app.core.project_trash import ProjectTrash
from app.core.workspace_paths import UnsafeWorkspacePath, project_directory
from app.models.schemas import (
    EngagementSummary,
    FindingDetail,
    FindingFrontmatter,
    FindingCreate,
)


class ScopeValidationError(ValueError):
    """Alcance inválido: target.yaml no se escribe hasta corregirlo."""


class FindingUpdateError(ValueError):
    pass


def _scope_module():
    scripts_dir = str(SCRIPTS_DIR)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    try:
        import seclab_scope
    except ImportError as exc:
        raise ScopeValidationError(f"No se pudo cargar el validador de alcance: {exc}") from exc
    return seclab_scope


def _validate_scope_payload(data: Dict[str, Any]) -> None:
    if not isinstance(data, dict) or not ({"scope", "authorization"} & set(data)):
        return
    module = _scope_module()
    try:
        module.validate_scope(data)
    except module.ScopeError as exc:
        raise ScopeValidationError(str(exc)) from exc


def _parse_frontmatter(content: str, strict: bool = False) -> Tuple[Dict[str, Any], str]:
    match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)(.*)\Z", content, re.DOTALL)
    if not match:
        if strict and content.startswith("---"):
            raise FindingUpdateError("Frontmatter inválido; no se sobrescribió la ficha.")
        return {}, content
    try:
        metadata = yaml.safe_load(match[1]) or {}
    except yaml.YAMLError as error:
        if strict:
            raise FindingUpdateError("Metadatos YAML inválidos; no se sobrescribió la ficha.") from error
        metadata = {}
    return metadata, match[2].strip()


class WorkspaceSyncService:
    def __init__(self, workspace_path: pathlib.Path = WORKSPACE_DIR):
        self.ws_path = workspace_path
        self.trash = ProjectTrash(workspace_path)
        self.ws_path.mkdir(parents=True, exist_ok=True)
        (self.ws_path / "engagements").mkdir(exist_ok=True)
        (self.ws_path / "retos").mkdir(exist_ok=True)

    def _resolve_dir(self, eng_id: str, eng_type: str = "engagement") -> pathlib.Path:
        return project_directory(self.ws_path, eng_id, eng_type)

    def list_engagements(self) -> List[EngagementSummary]:
        """Escanea el workspace y lista todos los engagements y retos registrados."""
        results = []
        for cat in ("engagements", "retos"):
            cat_dir = self.ws_path / cat
            if not cat_dir.exists() or cat_dir.is_symlink():
                continue
            for item in sorted(cat_dir.iterdir()):
                if item.is_symlink() or not item.is_dir() or item.name.startswith((".", "_")):
                    continue

                eng_id = item.name
                eng_type = "reto" if cat == "retos" else "engagement"
                try:
                    self._resolve_dir(eng_id, eng_type)
                except UnsafeWorkspacePath:
                    continue
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
                subtype = "machine" if eng_type == "reto" else None
                category = None
                points = None
                difficulty = None
                if target_yaml_path.exists():
                    try:
                        with open(target_yaml_path, "r") as yf:
                            ydata = yaml.safe_load(yf) or {}
                            eng_meta = ydata.get("engagement", {})
                            created_at = eng_meta.get("created_at")
                            client_name = eng_meta.get("client")
                            if eng_type == "reto":
                                subtype = eng_meta.get("subtype", "machine")
                                category = eng_meta.get("category")
                                points = eng_meta.get("points")
                                difficulty = eng_meta.get("difficulty")
                    except Exception:
                        pass

                # Verificar si está resuelto o si flags.json tiene metadata complementaria
                is_solved = False
                flags_file = item / "flags.json"
                if flags_file.exists():
                    try:
                        with open(flags_file, "r") as ff:
                            fdata = json.load(ff) or {}
                            if eng_type == "reto":
                                subtype = fdata.get("subtype") or subtype
                                category = fdata.get("category") or category
                                if fdata.get("points") is not None:
                                    points = fdata.get("points")
                                difficulty = fdata.get("difficulty") or difficulty
                                if subtype == "jeopardy":
                                    is_solved = (fdata.get("flag", {}).get("status") == "captured") or bool(fdata.get("solved"))
                                else:
                                    is_solved = (fdata.get("root_flag", {}).get("status") == "captured") or bool(fdata.get("solved"))
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
                        subtype=subtype,
                        category=category,
                        points=points,
                        difficulty=difficulty,
                        is_solved=is_solved,
                    )
                )
        return results

    def delete_engagement(self, eng_id: str, eng_type: str = "engagement") -> dict:
        return self.trash.move(eng_id, eng_type)

    def restore_engagement(self, entry_id: str, eng_id: str, eng_type: str = "engagement") -> dict:
        return self.trash.restore(entry_id, eng_id, eng_type)

    def create_engagement(
        self,
        name: str,
        eng_type: str = "engagement",
        domain: Optional[str] = None,
        client: Optional[str] = None,
        subtype: Optional[str] = None,
        category: Optional[str] = None,
        points: Optional[int] = None,
        difficulty: Optional[str] = None,
    ) -> EngagementSummary:
        """Crea la estructura de carpetas y siembra target.yaml, scope.txt y notes.md."""
        with self.trash.lock:
            clean_name = re.sub(r"[^a-zA-Z0-9._-]", "", name)
            target_dir = self._resolve_dir(clean_name, eng_type)
            if target_dir.exists():
                raise ValueError("Ya existe un proyecto con ese nombre.")
            scope_module = _scope_module()
            try:
                initial_scope = scope_module.initial_scope(domain)
            except scope_module.ScopeError as error:
                raise ScopeValidationError(str(error)) from error
            target_dir.mkdir(parents=True, exist_ok=False)

            for folder in ("recon", "fuzzing", "evidence", "loot", "screenshots"):
                (target_dir / folder).mkdir(exist_ok=True)

            # Sembrar target.yaml
            now_date = datetime.date.today().isoformat()
            sample_domain = (domain or "").strip()
            sample_client = client or ("Plataforma CTF" if eng_type == "reto" else clean_name.capitalize())

            clean_subtype = (subtype or "machine") if eng_type == "reto" else None

            target_yaml_data = {
                "version": "1.0",
                "engagement": {
                    "name": clean_name,
                    "type": eng_type,
                    "created_at": now_date,
                    "auditor": "tester",
                    "client": sample_client,
                    "tos_reference": "",
                    "emergency_contact": "",
                },
                "network": {
                    "vpn_profile": "none",
                    "assigned_ip": "",
                    "gateway_dns": "",
                },
                "scope": initial_scope,
                "authorization": scope_module.default_authorization(),
                "operational_limits": {
                    "max_requests_per_second": 1,
                    "max_parallel_threads": 1,
                    "max_probe_targets": 1000,
                    "probe_timeout_seconds": 8,
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

            if eng_type == "reto":
                target_yaml_data["engagement"]["subtype"] = clean_subtype
                if category:
                    target_yaml_data["engagement"]["category"] = category
                if points is not None:
                    target_yaml_data["engagement"]["points"] = points
                if difficulty:
                    target_yaml_data["engagement"]["difficulty"] = difficulty

                # Sembrar flags.json inicial
                initial_flags = {
                    "subtype": clean_subtype,
                    "category": category,
                    "points": points or (100 if clean_subtype == "jeopardy" else None),
                    "difficulty": difficulty or ("medium" if clean_subtype == "jeopardy" else None),
                    "solved": False,
                    "flag": {"value": "", "status": "pending", "captured_at": None, "notes": ""},
                    "user_flag": {"value": "", "status": "pending", "captured_at": None, "hash": ""},
                    "root_flag": {"value": "", "status": "pending", "captured_at": None, "hash": ""},
                    "custom_flags": [],
                }
                with open(target_dir / "flags.json", "w", encoding="utf-8") as ff:
                    json.dump(initial_flags, ff, indent=2, ensure_ascii=False)

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
                subtype=clean_subtype,
                category=category,
                points=points,
                difficulty=difficulty,
                is_solved=False,
            )

    def get_target_yaml(self, eng_id: str, eng_type: str = "engagement") -> Dict[str, Any]:
        """Lee y devuelve el contenido estructurado de target.yaml."""
        target_file = self._resolve_dir(eng_id, eng_type) / "target.yaml"
        if not target_file.exists():
            return {}
        with open(target_file, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def save_target_yaml(self, eng_id: str, data: Dict[str, Any], eng_type: str = "engagement") -> bool:
        """Guarda la especificación de alcance en target.yaml, validando antes de escribir."""
        _validate_scope_payload(data)
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
                    cvss_vector=fm_data.get("cvss_vector", fm_data.get("cvss_v31")),
                    cwe=fm_data.get("cwe"),
                    owasp=fm_data.get("owasp"),
                    asset=fm_data.get("asset"),
                    date=str(fm_data.get("date", datetime.date.today().isoformat())),
                    author=fm_data.get("author", "tester"),
                    status=str(fm_data.get("status") or "CANDIDATE").strip().upper() or "CANDIDATE",
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
        if not re.fullmatch(r"[a-zA-Z0-9-][a-zA-Z0-9._-]{0,127}", slug):
            raise UnsafeWorkspacePath("Identificador de hallazgo no válido.")
        file_path = self._resolve_dir(eng_id, eng_type) / "evidence" / f"{slug}.md"
        if not file_path.exists():
            return None
        content = file_path.read_text(encoding="utf-8")
        fm_data, body = _parse_frontmatter(content)
        fm = FindingFrontmatter(
            title=fm_data.get("title", slug.replace("-", " ").capitalize()),
            severity=str(fm_data.get("severity", "MEDIUM")).upper(),
            cvss_score=float(fm_data.get("cvss_score")) if fm_data.get("cvss_score") is not None else None,
            cvss_vector=fm_data.get("cvss_vector", fm_data.get("cvss_v31")),
            cwe=fm_data.get("cwe"),
            owasp=fm_data.get("owasp"),
            asset=fm_data.get("asset"),
            date=str(fm_data.get("date", datetime.date.today().isoformat())),
            author=fm_data.get("author", "tester"),
            status=str(fm_data.get("status") or "CANDIDATE").strip().upper() or "CANDIDATE",
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
        if not re.fullmatch(r"[a-zA-Z0-9-][a-zA-Z0-9._-]{0,127}", finding_create.slug):
            raise UnsafeWorkspacePath("Identificador de hallazgo no válido.")
        ev_dir = self._resolve_dir(eng_id, eng_type) / "evidence"
        ev_dir.mkdir(parents=True, exist_ok=True)
        file_path = ev_dir / f"{finding_create.slug}.md"

        if file_path.exists():
            if finding_create.body is None:
                raise FindingUpdateError("Para editar una ficha existente debes conservar su cuerpo Markdown completo.")
            fm, _ = _parse_frontmatter(file_path.read_text(encoding="utf-8"), strict=True)
            if not isinstance(fm, dict):
                raise FindingUpdateError("Los metadatos de la ficha no son válidos; no se sobrescribió.")
            for field in ("title", "severity", "cvss_score", "cvss_vector", "cwe", "asset", "status"):
                if field in finding_create.model_fields_set:
                    value = getattr(finding_create, field)
                    if field in ("severity", "status") and value is not None:
                        value = value.upper()
                    fm[field] = value
            content = f"---\n{yaml.dump(fm, default_flow_style=False, sort_keys=False, allow_unicode=True)}---\n\n{finding_create.body}"
            temporary = file_path.with_name(f".{file_path.name}.{uuid.uuid4().hex}.tmp")
            try:
                temporary.write_text(content, encoding="utf-8")
                temporary.chmod(file_path.stat().st_mode & 0o777)
                temporary.replace(file_path)
            finally:
                temporary.unlink(missing_ok=True)
            return self.get_finding(eng_id, finding_create.slug, eng_type)

        now_date = datetime.date.today().isoformat()
        fm = {
            "title": finding_create.title,
            "severity": finding_create.severity.upper(),
            "cvss_score": finding_create.cvss_score if finding_create.cvss_score is not None else 5.0,
            "cvss_vector": finding_create.cvss_vector or "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:L/A:N",
            "cwe": finding_create.cwe or "CWE-200",
            "asset": finding_create.asset or "",
            "date": now_date,
            "author": "tester",
            "status": (finding_create.status or "CANDIDATE").strip().upper() or "CANDIDATE",
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
        if not re.fullmatch(r"[a-zA-Z0-9-][a-zA-Z0-9._-]{0,127}", slug):
            raise UnsafeWorkspacePath("Identificador de hallazgo no válido.")
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

        cred_id = cred.get("id") or f"cred-{uuid.uuid4().hex}"
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
        target_yaml_file = target_dir / "target.yaml"
        target_meta = {}
        if target_yaml_file.exists():
            try:
                with open(target_yaml_file, "r", encoding="utf-8") as yf:
                    target_meta = (yaml.safe_load(yf) or {}).get("engagement", {})
            except Exception:
                pass

        data = {
            "subtype": target_meta.get("subtype", "machine"),
            "category": target_meta.get("category"),
            "points": target_meta.get("points"),
            "difficulty": target_meta.get("difficulty"),
            "solved": False,
            "flag": {"value": "", "status": "pending", "captured_at": None, "notes": ""},
            "user_flag": {"value": "", "status": "pending", "captured_at": None, "hash": ""},
            "root_flag": {"value": "", "status": "pending", "captured_at": None, "hash": ""},
            "custom_flags": [],
        }

        if flags_file.exists():
            try:
                with open(flags_file, "r", encoding="utf-8") as f:
                    file_data = json.load(f)
                    if isinstance(file_data, dict):
                        data.update(file_data)
            except Exception:
                pass

        if not isinstance(data.get("flag"), dict):
            data["flag"] = {"value": "", "status": "pending", "captured_at": None, "notes": ""}
        if not data.get("category"):
            data["category"] = target_meta.get("category")
        if data.get("points") is None:
            data["points"] = target_meta.get("points")
        if not data.get("difficulty"):
            data["difficulty"] = target_meta.get("difficulty")
        if not data.get("subtype"):
            data["subtype"] = target_meta.get("subtype", "machine")

        if data.get("subtype") == "jeopardy":
            data["solved"] = (data.get("flag", {}).get("status") == "captured") or bool(data.get("solved"))
        else:
            data["solved"] = (data.get("root_flag", {}).get("status") == "captured") or bool(data.get("solved"))

        return data

    def save_flags(self, eng_id: str, flags_data: dict, eng_type: str = "reto") -> dict:
        """Guarda el estado de banderas en flags.json y sincroniza metadatos en target.yaml."""
        target_dir = self._resolve_dir(eng_id, eng_type)
        target_dir.mkdir(parents=True, exist_ok=True)
        flags_file = target_dir / "flags.json"

        now_iso = datetime.datetime.now().isoformat()
        flag_obj = flags_data.setdefault("flag", {})
        if flag_obj.get("value") and flag_obj.get("status") == "captured":
            if not flag_obj.get("captured_at"):
                flag_obj["captured_at"] = now_iso
        elif flag_obj.get("status") == "pending":
            flag_obj["captured_at"] = None

        user_flag = flags_data.setdefault("user_flag", {})
        if user_flag.get("value") and user_flag.get("status") == "captured":
            if not user_flag.get("captured_at"):
                user_flag["captured_at"] = now_iso
        elif user_flag.get("status") == "pending":
            user_flag["captured_at"] = None

        root_flag = flags_data.setdefault("root_flag", {})
        if root_flag.get("value") and root_flag.get("status") == "captured":
            if not root_flag.get("captured_at"):
                root_flag["captured_at"] = now_iso
        elif root_flag.get("status") == "pending":
            root_flag["captured_at"] = None

        if flags_data.get("subtype") == "jeopardy":
            flags_data["solved"] = flag_obj.get("status") == "captured"
        else:
            flags_data["solved"] = root_flag.get("status") == "captured"

        with open(flags_file, "w", encoding="utf-8") as f:
            json.dump(flags_data, f, indent=2, ensure_ascii=False)

        target_yaml_file = target_dir / "target.yaml"
        if target_yaml_file.exists():
            try:
                with open(target_yaml_file, "r", encoding="utf-8") as yf:
                    ydata = yaml.safe_load(yf) or {}
                eng_meta = ydata.setdefault("engagement", {})
                updated_meta = False
                for field in ("category", "subtype", "difficulty", "points"):
                    if field in flags_data and flags_data[field] is not None:
                        eng_meta[field] = flags_data[field]
                        updated_meta = True
                if updated_meta:
                    with open(target_yaml_file, "w", encoding="utf-8") as yf:
                        yaml.dump(ydata, yf, default_flow_style=False, sort_keys=False, allow_unicode=True)
            except Exception:
                pass

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

        if not requested_path.is_relative_to(target_dir) or not requested_path.is_file():
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
