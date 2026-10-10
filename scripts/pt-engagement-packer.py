#!/usr/bin/env python3
"""Empaquetador Seguro, Sanitizador y Gestor de Cierre de Engagements para SecLab-SBF.

Provee empaquetado reproducible de informes y evidencias (REPORT.md, evidence/*.md, recon/),
sanitización automática de secretos y tokens (JWT, Bearer, Passwords, Cookies sensibles),
generación de manifiestos criptográficos de integridad (manifest.sha256) y cierre formal
de auditoría (status: closed en target.yaml).

Sin dependencias externas obligatorias (Python 3 stdlib).
"""

import argparse
import datetime
import hashlib
import importlib.machinery
import importlib.util
import json
import os
import pathlib
import re
import shutil
import sys
import tarfile
import zipfile
from typing import Any, Dict, List, Optional, Set, Tuple

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from seclab_artifacts import read_artifact_snapshot, HASH_LIMIT
from seclab_findings import requires_finding_review, finding_status_from_markdown

# Patrones para sanitización automática de credenciales
RE_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]+\b")
RE_AUTH_HEADER = re.compile(r"(?i)(Authorization:\s*(?:Bearer|Basic|Token)\s+)[^\r\n\"\'`]+")
RE_CURL_USER = re.compile(r"(?i)(curl\s+.*?--?(?:u|user)\s+[^:\s]+:)[^\s\"\'`]+")
RE_URL_CREDS = re.compile(r"https?://([^:/@\s]+):([^@/\s]+)@")
RE_COOKIE_SENSITIVE = re.compile(
    r"(?i)\b((?:session|PHPSESSID|JSESSIONID|token|auth|access_token|jwt|connect\.sid)=)[^;\r\n\"\'`]+"
)
RE_PRIVATE_KEY = re.compile(r"-----BEGIN [A-Z ]+ PRIVATE KEY-----[\s\S]*?-----END [A-Z ]+ PRIVATE KEY-----")


def sanitize_text(text: str) -> Tuple[str, int]:
    """Sanitiza tokens, contraseñas y credenciales sensibles en un texto.
    
    Devuelve la tupla (texto_sanitizado, total_reemplazos).
    """
    total_redactions = 0

    # 1. Private keys
    matches_pk = len(RE_PRIVATE_KEY.findall(text))
    if matches_pk > 0:
        text = RE_PRIVATE_KEY.sub("[REDACTED_PRIVATE_KEY]", text)
        total_redactions += matches_pk

    # 2. JWTs
    matches_jwt = len(RE_JWT.findall(text))
    if matches_jwt > 0:
        text = RE_JWT.sub("[REDACTED_JWT]", text)
        total_redactions += matches_jwt

    # 3. Auth headers
    def _auth_sub(m: re.Match) -> str:
        return f"{m.group(1)}[REDACTED_AUTH_TOKEN]"
    subbed_auth, count_auth = RE_AUTH_HEADER.subn(_auth_sub, text)
    if count_auth > 0:
        text = subbed_auth
        total_redactions += count_auth

    # 4. Curl user:pass
    def _curl_sub(m: re.Match) -> str:
        return f"{m.group(1)}[REDACTED_PASSWORD]"
    subbed_curl, count_curl = RE_CURL_USER.subn(_curl_sub, text)
    if count_curl > 0:
        text = subbed_curl
        total_redactions += count_curl

    # 5. URL user:pass
    def _url_sub(m: re.Match) -> str:
        return f"https://{m.group(1)}:[REDACTED_PASSWORD]@"
    subbed_url, count_url = RE_URL_CREDS.subn(_url_sub, text)
    if count_url > 0:
        text = subbed_url
        total_redactions += count_url

    # 6. Sensitive cookies
    def _cookie_sub(m: re.Match) -> str:
        return f"{m.group(1)}[REDACTED_SESSION]"
    subbed_cookie, count_cookie = RE_COOKIE_SENSITIVE.subn(_cookie_sub, text)
    if count_cookie > 0:
        text = subbed_cookie
        total_redactions += count_cookie

    return text, total_redactions


def compute_sha256(file_path: pathlib.Path) -> str:
    """Calcula el hash SHA-256 de un archivo."""
    hasher = hashlib.sha256()
    with file_path.open("rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def resolve_engagement_dir(target_arg: Optional[str] = None) -> Optional[pathlib.Path]:
    """Localiza el directorio del engagement basado en argumento o contexto actual."""
    if target_arg:
        p = pathlib.Path(target_arg).expanduser()
        if p.is_dir():
            return p.resolve()

        ws_env = os.environ.get("WORKSPACE_DIR")
        ws_dirs = [pathlib.Path(ws_env)] if ws_env else []
        ws_dirs.extend([
            pathlib.Path("/workspace"),
            pathlib.Path("./workspace"),
            pathlib.Path("."),
        ])

        for base in ws_dirs:
            for cat in ("engagements", "retos"):
                candidate = base / cat / target_arg
                if candidate.is_dir():
                    return candidate.resolve()
            candidate_direct = base / target_arg
            if candidate_direct.is_dir() and (candidate_direct / "target.yaml").is_file():
                return candidate_direct.resolve()

    cwd = pathlib.Path.cwd().resolve()
    if (cwd / "target.yaml").is_file() or (cwd / "evidence").is_dir() or (cwd / "REPORT.md").is_file():
        return cwd

    return None


def ensure_report_built(engagement_dir: pathlib.Path, artifact_reference_output=None, finding_source_output=None, report_hash_output=None) -> pathlib.Path:
    """Recompila con el alcance y las fichas actuales antes de cada exportación."""
    compiler_path = pathlib.Path(__file__).resolve().parent / "pt-report-compiler.py"
    if not compiler_path.is_file():
        compiler_path = pathlib.Path("/usr/local/bin/pt-report-compiler")
    if not compiler_path.is_file():
        raise ValueError("Reporte bloqueado: falta pt-report-compiler; reconstruye la imagen.")
    spec = importlib.util.spec_from_file_location("report_compiler", compiler_path,
            loader=importlib.machinery.SourceFileLoader("report_compiler", str(compiler_path)))
    if not spec or not spec.loader:
        raise ValueError("Reporte bloqueado: no se pudo cargar pt-report-compiler.")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.build_report(engagement_dir, artifact_reference_output=artifact_reference_output, finding_source_output=finding_source_output, report_hash_output=report_hash_output)


def pack_engagement(
    engagement_dir: pathlib.Path,
    output_path: Optional[pathlib.Path] = None,
    sanitize: bool = False,
    archive_format: str = "tar.gz",
) -> Dict[str, Any]:
    """Empaqueta los entregables del engagement con manifiesto SHA-256 y sanitización opcional."""
    if (engagement_dir / "REPORT.md").is_symlink():
        raise ValueError("Fuente de exportación no permitida: REPORT.md")
    references = {}
    finding_sources = []
    report_hash = {}
    report_file = ensure_report_built(engagement_dir, references, finding_sources, report_hash)
    expected_finding_hashes = {row["path"]: row["sha256"] for row in finding_sources}
    if not report_file or not report_file.is_file():
        raise ValueError("El reporte compilado está ausente; recompila antes de exportar.")
    eng_name = engagement_dir.name
    now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")

    # Determinar ruta de salida por defecto
    if not output_path:
        exports_dir = engagement_dir / "exports"
        exports_dir.mkdir(parents=True, exist_ok=True)
        ext = ".tar.gz" if archive_format == "tar.gz" else ".zip"
        output_path = exports_dir / f"{eng_name}_bundle_{now_str}{ext}"
    else:
        output_path = output_path.resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

    # Directorio temporal de staging para empaquetado
    staging_dir = engagement_dir / f".staging_pack_{now_str}"
    staging_dir.mkdir(parents=True, exist_ok=True)

    manifest_entries: List[str] = []
    total_redactions = 0
    packed_files: List[str] = []
    source_records = []
    source_hashes = {}

    def read_source(source):
        if source.is_symlink() or not source.resolve().is_relative_to(engagement_dir.resolve()):
            raise ValueError(f"Fuente de exportación no permitida: {source.name}")
        payload = source.read_bytes()
        source_hashes[str(source)] = hashlib.sha256(payload).hexdigest()
        return payload.decode("utf-8")

    def record_source(source, destination, relative):
        original_hash = source_hashes[str(source)]
        export_hash = compute_sha256(destination)
        source_records.append({"path": relative, "original_sha256": original_hash,
                               "export_sha256": export_hash,
                               "content_changed": original_hash != export_hash})

    try:
        # 1. REPORT.md
        if report_file and report_file.is_file():
            rep_text = read_source(report_file)
            if source_hashes[str(report_file)] != report_hash["sha256"]:
                raise ValueError("El reporte cambió después de compilar; recompila antes de exportar.")
            if sanitize:
                rep_text, red = sanitize_text(rep_text)
                total_redactions += red
            stg_rep = staging_dir / "REPORT.md"
            stg_rep.write_text(rep_text, encoding="utf-8")
            sha = compute_sha256(stg_rep)
            manifest_entries.append(f"{sha}  REPORT.md")
            packed_files.append("REPORT.md")
            record_source(report_file, stg_rep, "REPORT.md")

        # 2. target.yaml y scope.txt
        for cfg_name in ("target.yaml", "scope.txt", "notes.md"):
            src_cfg = engagement_dir / cfg_name
            if src_cfg.is_file():
                cfg_text = read_source(src_cfg)
                if sanitize and cfg_name == "notes.md":
                    cfg_text, red = sanitize_text(cfg_text)
                    total_redactions += red
                stg_cfg = staging_dir / cfg_name
                stg_cfg.write_text(cfg_text, encoding="utf-8")
                sha = compute_sha256(stg_cfg)
                manifest_entries.append(f"{sha}  {cfg_name}")
                packed_files.append(cfg_name)
                record_source(src_cfg, stg_cfg, cfg_name)

        # 3. evidence/*.md
        src_ev_dir = engagement_dir / "evidence"
        if src_ev_dir.is_dir():
            stg_ev_dir = staging_dir / "evidence"
            stg_ev_dir.mkdir(parents=True, exist_ok=True)
            for ev_file in sorted(src_ev_dir.glob("*.md")):
                if ev_file.name.startswith("_"):
                    continue
                ev_text = read_source(ev_file)
                relative = 'evidence/' + ev_file.name
                if relative in expected_finding_hashes and source_hashes[str(ev_file)] != expected_finding_hashes[relative]:
                    raise ValueError('La ficha cambió después de compilar; recompila antes de exportar: ' + relative)
                if sanitize:
                    ev_text, red = sanitize_text(ev_text)
                    total_redactions += red
                dest_ev = stg_ev_dir / ev_file.name
                dest_ev.write_text(ev_text, encoding="utf-8")
                sha = compute_sha256(dest_ev)
                rel_path = f"evidence/{ev_file.name}"
                manifest_entries.append(f"{sha}  {rel_path}")
                packed_files.append(rel_path)
                record_source(ev_file, dest_ev, rel_path)

        # 4. recon/ resúmenes
        src_recon = engagement_dir / "recon"
        if src_recon.is_dir():
            stg_recon = staging_dir / "recon"
            stg_recon.mkdir(parents=True, exist_ok=True)
            for recon_candidate in ("live_hosts.txt", "subdomains.txt", "summary.json",
                                    "probe_observations.jsonl", "recon.log", "urls_all.txt", "js_files.txt"):
                rf = src_recon / recon_candidate
                if rf.is_file():
                    rf_dest = stg_recon / recon_candidate
                    if rf.is_symlink() or not rf.resolve().is_relative_to(engagement_dir.resolve()):
                        raise ValueError(f"Fuente de exportación no permitida: recon/{recon_candidate}")
                    content = read_source(rf)
                    if sanitize:
                        content, red = sanitize_text(content)
                        total_redactions += red
                    rf_dest.write_text(content, encoding="utf-8")
                    sha = compute_sha256(rf_dest)
                    rel_path = f"recon/{recon_candidate}"
                    manifest_entries.append(f"{sha}  {rel_path}")
                    packed_files.append(rel_path)
                    record_source(rf, rf_dest, rel_path)

        terminal_log = engagement_dir / "terminal.log"
        if terminal_log.is_file():
            if terminal_log.is_symlink() or not terminal_log.resolve().is_relative_to(engagement_dir.resolve()):
                raise ValueError("Fuente de exportación no permitida: terminal.log")
            content = read_source(terminal_log)
            if sanitize:
                content, red = sanitize_text(content)
                total_redactions += red
            destination = staging_dir / "terminal.log"
            destination.write_text(content, encoding="utf-8")
            manifest_entries.append(f"{compute_sha256(destination)}  terminal.log")
            packed_files.append("terminal.log")
            record_source(terminal_log, destination, "terminal.log")

        source_manifest = staging_dir / "source-manifest.json"
        total = 0
        for relative, expected_hash in references.items():
            snapshot = read_artifact_snapshot(engagement_dir, relative, include_bytes=True)
            total += snapshot['size']
            if total > HASH_LIMIT or snapshot['sha256'] != expected_hash:
                raise ValueError('Artefacto vinculado cambiado o fuera del límite: ' + relative)
            payload = snapshot['_bytes']
            if sanitize and (snapshot['preview_status'] in ('binary', 'decoded_with_replacement') or b'\0' in payload):
                raise ValueError('No se puede sanitizar el artefacto vinculado binario: ' + relative)
            destination = staging_dir / relative
            if relative in packed_files:
                original = next(row['original_sha256'] for row in source_records if row['path'] == relative)
                if original != expected_hash:
                    raise ValueError('Artefacto cambió al exportar: ' + relative)
                continue
            if sanitize:
                try:
                    text = payload.decode('utf-8')
                except UnicodeDecodeError:
                    raise ValueError('No se puede sanitizar el artefacto vinculado no UTF-8: ' + relative) from None
                text, red = sanitize_text(text)
                total_redactions += red
                payload = text.encode('utf-8')
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(payload)
            manifest_entries.append(f'{compute_sha256(destination)}  {relative}')
            packed_files.append(relative)
            source_records.append({'path': relative, 'original_sha256': expected_hash,
                                   'export_sha256': compute_sha256(destination),
                                   'content_changed': expected_hash != compute_sha256(destination)})
        source_manifest.write_text(json.dumps({"schema_version": 1, "sanitized": sanitize,
            "files": source_records}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        manifest_entries.append(f"{compute_sha256(source_manifest)}  source-manifest.json")
        packed_files.append("source-manifest.json")

        records = {row['path']: row for row in source_records}
        finding_records = []
        for source in finding_sources:
            record = records.get(source['path'])
            if not record or record['original_sha256'] != source['sha256']:
                raise ValueError('Ficha cambiada o ausente al exportar: ' + source['path'])
            finding_records.append({
                'finding_id': source['finding_id'], 'identity_status': source['identity_status'],
                'source': record,
                'artifact_refs': [{**records[ref['path']], 'expected_sha256': ref['sha256']}
                                  for ref in source['artifact_refs']],
            })
        finding_manifest = staging_dir / 'finding-manifest.json'
        finding_manifest.write_text(json.dumps({'schema_version': 1, 'sanitized': sanitize,
            'report': records['REPORT.md'], 'findings': finding_records}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        manifest_entries.append(f'{compute_sha256(finding_manifest)}  finding-manifest.json')
        packed_files.append('finding-manifest.json')

        # 5. Generar manifest.sha256
        manifest_file = staging_dir / "manifest.sha256"
        manifest_file.write_text("\n".join(manifest_entries) + "\n", encoding="utf-8")
        packed_files.append("manifest.sha256")

        # 6. Crear archivo comprimido
        if archive_format == "zip":
            with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for root, _, files in os.walk(staging_dir):
                    for file in files:
                        full_p = pathlib.Path(root) / file
                        arcname = full_p.relative_to(staging_dir)
                        zf.write(full_p, arcname=f"{eng_name}/{arcname}")
        else:
            with tarfile.open(output_path, "w:gz") as tf:
                for root, _, files in os.walk(staging_dir):
                    for file in files:
                        full_p = pathlib.Path(root) / file
                        arcname = full_p.relative_to(staging_dir)
                        tf.add(full_p, arcname=f"{eng_name}/{arcname}")

    finally:
        # Limpiar staging
        if staging_dir.is_dir():
            shutil.rmtree(staging_dir, ignore_errors=True)

    archive_sha256 = compute_sha256(output_path)
    archive_size = output_path.stat().st_size

    return {
        "status": "success",
        "engagement": eng_name,
        "archive_path": str(output_path),
        "archive_sha256": archive_sha256,
        "archive_size": archive_size,
        "files_packed": len(packed_files),
        "redactions_count": total_redactions,
        "sanitized": sanitize,
        "timestamp": now_str,
    }


def check_closure_readiness(engagement_dir: pathlib.Path) -> Tuple[bool, List[str], List[str]]:
    """Verifica si el engagement cumple con los requisitos de calidad para cierre."""
    # 1. Intentar delegar a AuditChecklistEvaluator si está disponible
    candidate_checklist_paths = [
        pathlib.Path(__file__).resolve().parent / "pt-audit-checklist.py",
        pathlib.Path(__file__).resolve().parent / "pt-audit-checklist",
        pathlib.Path("/usr/local/bin/pt-audit-checklist"),
        pathlib.Path("./scripts/pt-audit-checklist.py"),
    ]
    for cp in candidate_checklist_paths:
        if cp.is_file():
            try:
                spec = importlib.util.spec_from_file_location("pt_audit_checklist", cp,
                    loader=importlib.machinery.SourceFileLoader("pt_audit_checklist", str(cp)))
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    if hasattr(mod, "AuditChecklistEvaluator"):
                        res = mod.AuditChecklistEvaluator(engagement_dir).evaluate()
                        readiness = res.get("readiness", {})
                        return (
                            readiness.get("ready_for_closure", True),
                            readiness.get("blocking_issues", []),
                            readiness.get("recommendations", []),
                        )
            except Exception:
                pass

    # 2. Fallback determinista autónomo
    blocking: List[str] = []
    recommendations: List[str] = []

    target_yaml = engagement_dir / "target.yaml"
    scope_txt = engagement_dir / "scope.txt"
    if not target_yaml.is_file() and not scope_txt.is_file():
        blocking.append("No se encontró target.yaml ni scope.txt")

    ev_dir = engagement_dir / "evidence"
    unverified: List[str] = []
    finding_count = 0
    if ev_dir.is_dir():
        for f in sorted(ev_dir.glob("*.md")):
            if f.name.startswith(("_", ".")) or f.name.lower() == "readme.md":
                continue
            finding_count += 1
            try:
                content = f.read_text(encoding="utf-8")
                status = finding_status_from_markdown(content)
                fid = f.stem.upper()
                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        for line in parts[1].splitlines():
                            if line.strip().startswith("id:"):
                                fid = line.split(":", 1)[1].strip().strip("'\"")
                if requires_finding_review(status):
                    unverified.append(fid)
            except Exception:
                pass

    if unverified:
        blocking.append(f"Existen hallazgos sin verificar formalmente: {', '.join(unverified)}")

    report_md = engagement_dir / "REPORT.md"
    if not report_md.is_file() and finding_count > 0:
        blocking.append("El informe final REPORT.md no ha sido compilado (ejecute: pt-report build)")

    return len(blocking) == 0, blocking, recommendations


def close_engagement(engagement_dir: pathlib.Path, force: bool = False) -> Dict[str, Any]:
    """Cierra formalmente un engagement actualizando target.yaml y verificando compuertas de calidad."""
    eng_name = engagement_dir.name
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    target_yaml = engagement_dir / "target.yaml"

    ready, blocking_issues, recommendations = check_closure_readiness(engagement_dir)
    if not ready and not force:
        return {
            "status": "blocked",
            "forced": False,
            "engagement": eng_name,
            "directory": str(engagement_dir),
            "ready_for_closure": False,
            "blocking_issues": blocking_issues,
            "recommendations": recommendations,
            "message": "Cierre bloqueado por compuerta de calidad. Use --force para omitir estas comprobaciones.",
        }

    updated_target = False
    if target_yaml.is_file():
        lines = target_yaml.read_text(encoding="utf-8").splitlines()
        new_lines: List[str] = []
        in_eng_sec = False
        has_status = False
        has_closed_at = False

        for line in lines:
            if line.startswith("engagement:"):
                in_eng_sec = True
                new_lines.append(line)
                continue
            elif in_eng_sec and not line.startswith(" ") and not line.startswith("\t"):
                if not has_status:
                    new_lines.append("  status: closed")
                if not has_closed_at:
                    new_lines.append(f"  closed_at: '{now_iso}'")
                in_eng_sec = False

            if in_eng_sec and line.strip().startswith("status:"):
                new_lines.append("  status: closed")
                has_status = True
            elif in_eng_sec and line.strip().startswith("closed_at:"):
                new_lines.append(f"  closed_at: '{now_iso}'")
                has_closed_at = True
            else:
                new_lines.append(line)

        if in_eng_sec:
            if not has_status:
                new_lines.append("  status: closed")
            if not has_closed_at:
                new_lines.append(f"  closed_at: '{now_iso}'")

        target_yaml.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        updated_target = True

    # Comprobar checklist post-engagement
    checklist = {
        "report_compiled": (engagement_dir / "REPORT.md").is_file(),
        "target_status_closed": updated_target,
        "clean_up_callbacks_recommended": True,
        "clean_up_audit_logs_recommended": True,
    }

    res: Dict[str, Any] = {
        "status": "closed",
        "forced": force and not ready,
        "engagement": eng_name,
        "closed_at": now_iso,
        "directory": str(engagement_dir),
        "target_yaml_updated": updated_target,
        "checklist": checklist,
    }
    if force and not ready:
        res["bypassed_issues"] = blocking_issues
    return res


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Empaquetador Seguro, Sanitizador y Cierre de Engagements de SecLab-SBF (pt-eng pack/close).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="Subcomandos disponibles")

    # pack
    p_pack = subparsers.add_parser("pack", help="Empaqueta informe y evidencias con manifiesto SHA-256")
    p_pack.add_argument("engagement", nargs="?", help="Ruta o nombre del engagement a empaquetar")
    p_pack.add_argument("-o", "--output", help="Ruta de destino del archivo generado (.tar.gz o .zip)")
    p_pack.add_argument("-s", "--sanitize", action="store_true", help="Ofuscar tokens, JWTs y passwords sensibles")
    p_pack.add_argument("--format", choices=["tar.gz", "zip"], default="tar.gz", help="Formato de compresión")
    p_pack.add_argument("-j", "--json", action="store_true", help="Salida en formato JSON estructurado")

    # close
    p_close = subparsers.add_parser("close", help="Sella y cierra formalmente la auditoría en target.yaml")
    p_close.add_argument("engagement", nargs="?", help="Ruta o nombre del engagement a cerrar")
    p_close.add_argument("-f", "--force", action="store_true", help="Forzar el cierre omitiendo comprobaciones de calidad")
    p_close.add_argument("-j", "--json", action="store_true", help="Salida en formato JSON estructurado")

    # sanitize (standalone)
    p_san = subparsers.add_parser("sanitize", help="Sanitiza un archivo o texto plano en stdout")
    p_san.add_argument("file", help="Archivo a sanitizar")
    p_san.add_argument("-o", "--output", help="Archivo de salida (si se omite, imprime en stdout)")

    args = parser.parse_args()

    if not args.subcommand:
        parser.print_help(sys.stderr)
        return 2

    if args.subcommand == "sanitize":
        f_path = pathlib.Path(args.file)
        if not f_path.is_file():
            print(f"Error: Archivo no encontrado: {f_path}", file=sys.stderr)
            return 1
        content = f_path.read_text(encoding="utf-8")
        clean_text, count = sanitize_text(content)
        if args.output:
            out_p = pathlib.Path(args.output)
            out_p.write_text(clean_text, encoding="utf-8")
            print(f"[+] Archivo sanitizado guardado en: {out_p} ({count} ofuscaciones)")
        else:
            print(clean_text)
        return 0

    eng_dir = resolve_engagement_dir(args.engagement)
    if not eng_dir or not eng_dir.is_dir():
        print(f"Error: No se pudo localizar el directorio del engagement: {args.engagement or 'no especificado'}", file=sys.stderr)
        return 1

    if args.subcommand == "pack":
        out_p = pathlib.Path(args.output).resolve() if args.output else None
        try:
            res = pack_engagement(eng_dir, output_path=out_p, sanitize=args.sanitize, archive_format=args.format)
        except (ValueError, OSError, ImportError) as error:
            if args.json:
                print(json.dumps({"status": "blocked", "message": str(error)}, ensure_ascii=False))
            else:
                print(f"[!] Exportación bloqueada: {error}", file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(f"\n\033[32m[+] Paquete de engagement generado con éxito:\033[0m")
            print(f"    Engagement:       {res['engagement']}")
            print(f"    Archivo:          {res['archive_path']}")
            print(f"    Archivos empaq:   {res['files_packed']} (incluye manifest.sha256)")
            print(f"    Sanitizado:       {'Sí (' + str(res['redactions_count']) + ' ofuscaciones)' if res['sanitized'] else 'No'}")
            print(f"    SHA-256 Bundle:   {res['archive_sha256']}")
            print(f"    Tamaño:           {res['archive_size']} bytes\n")
        return 0

    elif args.subcommand == "close":
        res = close_engagement(eng_dir, force=args.force)
        if args.json:
            print(json.dumps(res, indent=2))
            return 1 if res.get("status") == "blocked" else 0

        if res.get("status") == "blocked":
            print(f"\n\033[31m[!] Cierre bloqueado por compuerta de calidad para {res['engagement']}:\033[0m")
            for issue in res.get("blocking_issues", []):
                print(f"    - ❌ {issue}")
            print("\n  Para corregir:")
            print("    - Verifica hallazgos en evidence/*.md (status: Confirmado)")
            print("    - Compila el reporte: pt-report build")
            print("    - O fuerza el cierre con: pt-eng close --force\n")
            return 1

        if res.get("forced"):
            print(f"\n\033[33m[!] Advertencia: Engagement cerrado con --force (requisitos omitidos):\033[0m")
            for issue in res.get("bypassed_issues", []):
                print(f"    - ⚠️ {issue}")
        else:
            print(f"\n\033[32m[+] Engagement cerrado satisfactoriamente:\033[0m")

        print(f"    Engagement:        {res['engagement']}")
        print(f"    Fecha de cierre:   {res['closed_at']}")
        print(f"    target.yaml:       {'Actualizado a status: closed' if res['target_yaml_updated'] else 'No encontrado'}")
        print("\n  Recordatorios post-engagement:")
        print("    1. Detén receptores OOB si siguen activos: pt-callback stop")
        print("    2. Detén la bitácora si sigue grabando:   pt-log stop")
        print("    3. Genera el entregable sanitizado:       pt-eng pack --sanitize\n")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
