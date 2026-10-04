#!/usr/bin/env python3
"""Pipeline Automatizado y Seguro de Reconocimiento con Scope Guard para SecLab-SBF.

Orquesta la recolección pasiva y activa de superficie de ataque (subdominios, sondeo
de servicios HTTP/HTTPS, cosecha de URLs y patrones de vulnerabilidad gf), aplicando
filtrado estricto de alcance (Scope Guard) antes de emitir tráfico de red y
estructurando los resultados en recon/ para consumo de agentes y reportes.

Sin dependencias externas obligatorias (Python 3 stdlib).
"""

import argparse
import datetime
import ipaddress
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

URL_HOST_RE = re.compile(r"^(?:https?://)?([^/:]+)(?::\d+)?(?:/.*)?$", re.IGNORECASE)
IPV4_RE = re.compile(r"^(\d{1,3}\.){3}\d{1,3}$")

# Patrones estándar de clasificación gf
DEFAULT_GF_PATTERNS = ["xss", "sqli", "ssrf", "redirect", "idor", "rce", "lfi"]


def normalize_target(raw_target: str) -> str:
    """Extrae el hostname o IP limpia de una URL, host:puerto o ruta."""
    cleaned = raw_target.strip()
    match = URL_HOST_RE.match(cleaned)
    if match:
        return match.group(1).lower()
    return cleaned.split(":")[0].split("/")[0].lower()


def is_ip(target: str) -> bool:
    """Verifica si el objetivo es una dirección IP válida."""
    try:
        ipaddress.ip_address(target)
        return True
    except ValueError:
        return False


def domain_matches(target: str, pattern: str) -> bool:
    """Verifica si target coincide con pattern (exacto o wildcard *.dominio)."""
    target = target.lower().strip()
    pattern = pattern.lower().strip()
    if pattern.startswith("*."):
        suffix = pattern[2:]
        return target == suffix or target.endswith("." + suffix)
    return target == pattern or target.endswith("." + pattern)


def parse_simple_yaml_lists(content: str) -> Dict[str, Any]:
    """Parser ligero de respaldo para target.yaml sin dependencias externas."""
    data: Dict[str, Any] = {
        "scope": {
            "in_scope": {"domains": [], "ips": [], "cidrs": [], "endpoints": []},
            "out_of_scope": {"domains": [], "ips": [], "cidrs": [], "notes": []},
        },
        "operational_limits": {},
        "engagement": {},
    }

    current_section = None
    current_sub = None
    current_list = None

    for line in content.splitlines():
        line_str = line.strip()
        if not line_str or line_str.startswith("#"):
            continue

        if line.startswith("engagement:"):
            current_section = "engagement"
            continue
        elif line.startswith("scope:"):
            current_section = "scope"
            continue
        elif line.startswith("operational_limits:"):
            current_section = "operational_limits"
            continue

        if current_section == "scope":
            if line.startswith("  in_scope:"):
                current_sub = "in_scope"
                current_list = None
                continue
            elif line.startswith("  out_of_scope:"):
                current_sub = "out_of_scope"
                current_list = None
                continue

            if current_sub in ("in_scope", "out_of_scope"):
                list_match = re.match(r"^\s{4}([a-z_]+):(?:\s*\[(.*)\])?", line)
                if list_match:
                    key = list_match.group(1)
                    inline_items = list_match.group(2)
                    current_list = key
                    if inline_items is not None:
                        items = [i.strip(" '\"") for i in inline_items.split(",") if i.strip(" '\"")]
                        data["scope"][current_sub][key] = items
                    elif key not in data["scope"][current_sub]:
                        data["scope"][current_sub][key] = []
                    continue

                item_match = re.match(r"^\s{6}-\s*[\"']?([^\"']+)[\"']?", line)
                if item_match and current_list:
                    item_val = item_match.group(1).strip()
                    if current_list not in data["scope"][current_sub]:
                        data["scope"][current_sub][current_list] = []
                    data["scope"][current_sub][current_list].append(item_val)

        elif current_section in ("engagement", "operational_limits"):
            kv_match = re.match(r"^\s{2}([a-z_]+):\s*[\"']?([^\"']+)[\"']?", line)
            if kv_match:
                k, v = kv_match.group(1), kv_match.group(2).strip()
                data[current_section][k] = v

    return data


def load_scope_rules(engagement_dir: pathlib.Path) -> Dict[str, Any]:
    """Carga target.yaml o scope.txt del engagement."""
    target_yaml = engagement_dir / "target.yaml"
    if target_yaml.is_file():
        content = target_yaml.read_text(encoding="utf-8")
        try:
            import yaml  # type: ignore

            loaded = yaml.safe_load(content)
            if isinstance(loaded, dict):
                return loaded
        except Exception:
            pass
        return parse_simple_yaml_lists(content)

    scope_txt = engagement_dir / "scope.txt"
    if scope_txt.is_file():
        in_scope_domains: List[str] = []
        out_scope_domains: List[str] = []
        current_section = None
        for line in scope_txt.read_text(encoding="utf-8").splitlines():
            line_clean = line.strip()
            if line_clean.startswith("## Activos y Objetivos en Alcance"):
                current_section = "in"
                continue
            elif line_clean.startswith("## Fuera de Alcance"):
                current_section = "out"
                continue
            elif line_clean.startswith("## "):
                current_section = None
                continue

            if line_clean.startswith("- "):
                item = line_clean[2:].strip().split()[0].strip("[]()")
                if item:
                    norm = normalize_target(item)
                    if current_section == "in":
                        in_scope_domains.append(norm)
                    elif current_section == "out":
                        out_scope_domains.append(norm)

        return {
            "engagement": {"name": engagement_dir.name},
            "scope": {
                "in_scope": {"domains": in_scope_domains, "ips": [], "cidrs": [], "endpoints": []},
                "out_of_scope": {"domains": out_scope_domains, "ips": [], "cidrs": [], "notes": []},
            },
            "operational_limits": {},
        }

    return {
        "engagement": {"name": engagement_dir.name},
        "scope": {
            "in_scope": {"domains": [], "ips": [], "cidrs": [], "endpoints": []},
            "out_of_scope": {"domains": [], "ips": [], "cidrs": [], "notes": []},
        },
        "operational_limits": {},
    }


def check_scope(target: str, scope_data: Dict[str, Any]) -> Tuple[str, str]:
    """Evalúa si target es OUT_OF_SCOPE, IN_SCOPE o UNKNOWN.

    Retorna: (veredicto, regla_coincidente)
    """
    clean_target = normalize_target(target)
    scope = scope_data.get("scope", {})
    in_scope = scope.get("in_scope", {})
    out_of_scope = scope.get("out_of_scope", {})

    target_is_ip = is_ip(clean_target)
    target_addr = ipaddress.ip_address(clean_target) if target_is_ip else None

    # 1. EVALUAR PRIMERO EXCLUSIONES (OUT_OF_SCOPE)
    if target_is_ip and target_addr:
        for o_ip in out_of_scope.get("ips", []):
            try:
                if target_addr == ipaddress.ip_address(o_ip.strip()):
                    return ("OUT_OF_SCOPE", f"IP excluida: {o_ip}")
            except ValueError:
                pass
        for o_cidr in out_of_scope.get("cidrs", []):
            try:
                if target_addr in ipaddress.ip_network(o_cidr.strip(), strict=False):
                    return ("OUT_OF_SCOPE", f"CIDR excluido: {o_cidr}")
            except ValueError:
                pass
    else:
        for o_dom in out_of_scope.get("domains", []):
            if domain_matches(clean_target, o_dom):
                return ("OUT_OF_SCOPE", f"Dominio excluido: {o_dom}")

    # 2. EVALUAR COINCIDENCIA EN ALCANCE (IN_SCOPE)
    if target_is_ip and target_addr:
        for i_ip in in_scope.get("ips", []):
            try:
                if target_addr == ipaddress.ip_address(i_ip.strip()):
                    return ("IN_SCOPE", f"IP autorizada: {i_ip}")
            except ValueError:
                pass
        for i_cidr in in_scope.get("cidrs", []):
            try:
                if target_addr in ipaddress.ip_network(i_cidr.strip(), strict=False):
                    return ("IN_SCOPE", f"CIDR autorizado: {i_cidr}")
            except ValueError:
                pass
    else:
        for i_dom in in_scope.get("domains", []):
            if domain_matches(clean_target, i_dom):
                return ("IN_SCOPE", f"Dominio autorizado: {i_dom}")

    # 3. NO COINCIDE CON NINGUNA REGLA
    return ("UNKNOWN", "Objetivo no listado en el alcance explícito")


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
            if candidate_direct.is_dir():
                return candidate_direct.resolve()

    cwd = pathlib.Path.cwd().resolve()
    if (cwd / "target.yaml").is_file() or (cwd / "recon").is_dir() or (cwd / "evidence").is_dir() or (cwd / "scope.txt").is_file():
        return cwd

    if "TMUX" in os.environ:
        try:
            res = subprocess.run(
                ["tmux", "show-option", "-pv", "@seclab_log_file"],
                capture_output=True,
                text=True,
                check=False,
            )
            log_path = res.stdout.strip()
            if log_path:
                log_file = pathlib.Path(log_path)
                if log_file.parent.is_dir():
                    return log_file.parent.resolve()
        except Exception:
            pass

    return None


def detect_tools() -> Dict[str, Optional[str]]:
    """Detecta los binarios disponibles en PATH para el pipeline."""
    tools = [
        "subfinder",
        "assetfinder",
        "findomain",
        "httpx",
        "httprobe",
        "gau",
        "waybackurls",
        "gf",
    ]
    return {tool: shutil.which(tool) for tool in tools}


def record_audit_mark(engagement_dir: pathlib.Path, mark_text: str) -> None:
    """Registra un hito de auditoría en terminal.log o sesión de tmux activa."""
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    mark_line = f"\n>>> [{now_iso}] [AUDIT-MARK] {mark_text} <<<\n"

    # 1. Si hay log en el engagement
    term_log = engagement_dir / "terminal.log"
    if term_log.is_file() or (engagement_dir / "target.yaml").is_file():
        try:
            with open(term_log, "a", encoding="utf-8") as f:
                f.write(mark_line)
        except Exception:
            pass

    # 2. Si hay TMUX activo
    if "TMUX" in os.environ:
        try:
            res = subprocess.run(
                ["tmux", "show-option", "-pv", "@seclab_log_file"],
                capture_output=True,
                text=True,
                check=False,
            )
            tmux_log = res.stdout.strip()
            if tmux_log and os.path.isfile(tmux_log) and tmux_log != str(term_log):
                with open(tmux_log, "a", encoding="utf-8") as f:
                    f.write(mark_line)
        except Exception:
            pass


class ReconPipeline:
    """Orquestador seguro del pipeline de reconocimiento."""

    def __init__(self, engagement_dir: pathlib.Path, dry_run: bool = False):
        self.engagement_dir = engagement_dir.resolve()
        self.recon_dir = self.engagement_dir / "recon"
        self.patterns_dir = self.recon_dir / "patterns"
        self.dry_run = dry_run
        self.scope_data = load_scope_rules(self.engagement_dir)
        self.tools = detect_tools()

    def prepare_directories(self) -> None:
        """Asegura la estructura requerida en recon/."""
        self.recon_dir.mkdir(parents=True, exist_ok=True)
        self.patterns_dir.mkdir(parents=True, exist_ok=True)

    def get_in_scope_domains(self) -> List[str]:
        """Extrae la lista de dominios base autorizados."""
        scope = self.scope_data.get("scope", {})
        in_scope = scope.get("in_scope", {})
        domains = in_scope.get("domains", [])
        return [d.strip() for d in domains if d.strip()]

    def filter_domains_by_scope(self, raw_targets: List[str]) -> Tuple[List[str], List[Dict[str, str]]]:
        """Filtra una lista de objetivos contra las reglas de scope."""
        in_scope_targets: List[str] = []
        discarded: List[Dict[str, str]] = []

        seen: Set[str] = set()
        for raw in raw_targets:
            target = raw.strip()
            if not target:
                continue
            norm = normalize_target(target)
            if norm in seen:
                continue
            seen.add(norm)

            verdict, reason = check_scope(norm, self.scope_data)
            if verdict == "IN_SCOPE":
                in_scope_targets.append(norm)
            else:
                discarded.append({
                    "target": norm,
                    "verdict": verdict,
                    "reason": reason,
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                })

        return sorted(in_scope_targets), discarded

    def run_subdomain_enumeration(self) -> Dict[str, Any]:
        """Etapa 1: Enumeración Pasiva/DNS con filtrado estricto de scope."""
        base_domains = self.get_in_scope_domains()
        if not base_domains:
            return {"error": "No hay dominios autorizados en in_scope.domains de target.yaml/scope.txt"}

        discovered_raw: Set[str] = set()

        # Si ya existe un subdomains.txt existente, preservarlo
        sub_file = self.recon_dir / "subdomains.txt"
        if sub_file.is_file():
            for line in sub_file.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    discovered_raw.add(line.strip())

        # Si estamos en dry-run, simular
        if self.dry_run:
            for d in base_domains:
                clean_dom = d.lstrip("*.")
                discovered_raw.add(clean_dom)
                discovered_raw.add(f"api.{clean_dom}")
                discovered_raw.add(f"admin.{clean_dom}")
        else:
            for domain in base_domains:
                clean_dom = domain.lstrip("*.")
                discovered_raw.add(clean_dom)

                # Subfinder
                if self.tools.get("subfinder"):
                    try:
                        res = subprocess.run(
                            [self.tools["subfinder"], "-d", clean_dom, "-silent"],
                            capture_output=True,
                            text=True,
                            timeout=180,
                            check=False,
                        )
                        for line in res.stdout.splitlines():
                            if line.strip():
                                discovered_raw.add(line.strip())
                    except Exception:
                        pass

                # Assetfinder
                if self.tools.get("assetfinder"):
                    try:
                        res = subprocess.run(
                            [self.tools["assetfinder"], "--subs-only", clean_dom],
                            capture_output=True,
                            text=True,
                            timeout=120,
                            check=False,
                        )
                        for line in res.stdout.splitlines():
                            if line.strip():
                                discovered_raw.add(line.strip())
                    except Exception:
                        pass

                # Findomain
                if self.tools.get("findomain"):
                    try:
                        res = subprocess.run(
                            [self.tools["findomain"], "-t", clean_dom, "-q"],
                            capture_output=True,
                            text=True,
                            timeout=120,
                            check=False,
                        )
                        for line in res.stdout.splitlines():
                            if line.strip():
                                discovered_raw.add(line.strip())
                    except Exception:
                        pass

        # Filtrar objetivos descubiertos con Scope Guard
        valid_subs, discarded_subs = self.filter_domains_by_scope(list(discovered_raw))

        if not self.dry_run:
            # Escribir subdomains.txt
            sub_file.write_text("\n".join(valid_subs) + ("\n" if valid_subs else ""), encoding="utf-8")

            # Escribir descartados
            if discarded_subs:
                discarded_file = self.recon_dir / "out_of_scope_discarded.txt"
                lines = [f"[{d['timestamp']}] {d['target']} -> {d['verdict']}: {d['reason']}" for d in discarded_subs]
                discarded_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

        return {
            "stage": "subdomains",
            "total_raw": len(discovered_raw),
            "in_scope_count": len(valid_subs),
            "discarded_count": len(discarded_subs),
            "subdomains": valid_subs,
            "discarded": discarded_subs,
        }

    def run_live_probing(self) -> Dict[str, Any]:
        """Etapa 2: Sondeo Activo de Servicios Web (HTTP/HTTPS)."""
        sub_file = self.recon_dir / "subdomains.txt"
        live_hosts: List[str] = []

        if not sub_file.is_file():
            return {"error": "No existe recon/subdomains.txt. Ejecute primero la etapa 'subdomains'"}

        subs = [l.strip() for l in sub_file.read_text(encoding="utf-8").splitlines() if l.strip()]
        if not subs:
            return {"stage": "probe", "live_hosts_count": 0, "live_hosts": []}

        if self.dry_run:
            live_hosts = [f"https://{s}" for s in subs]
        else:
            # Preferir httpx
            if self.tools.get("httpx"):
                try:
                    res = subprocess.run(
                        [self.tools["httpx"], "-l", str(sub_file), "-silent", "-no-color"],
                        capture_output=True,
                        text=True,
                        timeout=300,
                        check=False,
                    )
                    for line in res.stdout.splitlines():
                        if line.strip() and line.startswith("http"):
                            live_hosts.append(line.strip())
                except Exception:
                    pass
            # Fallback a httprobe
            elif self.tools.get("httprobe"):
                try:
                    proc = subprocess.Popen(
                        [self.tools["httprobe"], "-c", "40"],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                    )
                    stdout, _ = proc.communicate(input="\n".join(subs))
                    for line in stdout.splitlines():
                        if line.strip() and line.startswith("http"):
                            live_hosts.append(line.strip())
                except Exception:
                    pass
            else:
                # Si ninguna tool está en PATH, fallback heurístico
                live_hosts = [f"https://{s}" for s in subs]

        # Validar que los hosts de live_hosts sigan dentro de scope
        valid_live: List[str] = []
        for host in sorted(set(live_hosts)):
            verdict, _ = check_scope(host, self.scope_data)
            if verdict == "IN_SCOPE":
                valid_live.append(host)

        if not self.dry_run:
            live_file = self.recon_dir / "live_hosts.txt"
            live_file.write_text("\n".join(valid_live) + ("\n" if valid_live else ""), encoding="utf-8")

        return {
            "stage": "probe",
            "live_hosts_count": len(valid_live),
            "live_hosts": valid_live,
        }

    def run_url_harvesting(self) -> Dict[str, Any]:
        """Etapa 3: Cosecha de URLs Históricas & Endpoints con Filtrado de Scope."""
        base_domains = self.get_in_scope_domains()
        raw_urls: Set[str] = set()

        if self.dry_run:
            for d in base_domains:
                clean_dom = d.lstrip("*.")
                raw_urls.add(f"https://{clean_dom}/api/v1/users?id=1")
                raw_urls.add(f"https://{clean_dom}/static/js/app.bundle.js")
                raw_urls.add(f"https://{clean_dom}/redirect?url=https://other.com")
        else:
            for domain in base_domains:
                clean_dom = domain.lstrip("*.")
                # gau
                if self.tools.get("gau"):
                    try:
                        res = subprocess.run(
                            [self.tools["gau"], "--subs", clean_dom],
                            capture_output=True,
                            text=True,
                            timeout=180,
                            check=False,
                        )
                        for line in res.stdout.splitlines():
                            if line.strip() and line.startswith("http"):
                                raw_urls.add(line.strip())
                    except Exception:
                        pass

                # waybackurls
                if self.tools.get("waybackurls"):
                    try:
                        res = subprocess.run(
                            [self.tools["waybackurls"], clean_dom],
                            capture_output=True,
                            text=True,
                            timeout=180,
                            check=False,
                        )
                        for line in res.stdout.splitlines():
                            if line.strip() and line.startswith("http"):
                                raw_urls.add(line.strip())
                    except Exception:
                        pass

        # Filtrar URLs para asegurar que pertenezcan a hosts autorizados
        valid_urls: List[str] = []
        js_files: List[str] = []

        for url in sorted(raw_urls):
            verdict, _ = check_scope(url, self.scope_data)
            if verdict == "IN_SCOPE":
                valid_urls.append(url)
                if re.search(r"\.js(\?|$)", url, re.IGNORECASE):
                    js_files.append(url)

        if not self.dry_run:
            urls_file = self.recon_dir / "urls_all.txt"
            urls_file.write_text("\n".join(valid_urls) + ("\n" if valid_urls else ""), encoding="utf-8")

            js_file = self.recon_dir / "js_files.txt"
            js_file.write_text("\n".join(js_files) + ("\n" if js_files else ""), encoding="utf-8")

        return {
            "stage": "urls",
            "urls_count": len(valid_urls),
            "js_files_count": len(js_files),
        }

    def run_pattern_classification(self) -> Dict[str, Any]:
        """Etapa 4: Clasificación Heurística de Parámetros con gf."""
        urls_file = self.recon_dir / "urls_all.txt"
        pattern_results: Dict[str, int] = {}

        if not urls_file.is_file():
            return {"error": "No existe recon/urls_all.txt para clasificar patrones"}

        urls_text = urls_file.read_text(encoding="utf-8")
        all_urls = [l.strip() for l in urls_text.splitlines() if l.strip()]

        if self.dry_run:
            for pat in DEFAULT_GF_PATTERNS:
                pattern_results[pat] = 1 if all_urls else 0
        elif self.tools.get("gf") and all_urls:
            for pat in DEFAULT_GF_PATTERNS:
                try:
                    res = subprocess.run(
                        [self.tools["gf"], pat, str(urls_file)],
                        capture_output=True,
                        text=True,
                        timeout=60,
                        check=False,
                    )
                    matches = [l.strip() for l in res.stdout.splitlines() if l.strip()]
                    if matches:
                        out_pat = self.patterns_dir / f"{pat}.txt"
                        out_pat.write_text("\n".join(matches) + "\n", encoding="utf-8")
                        pattern_results[pat] = len(matches)
                    else:
                        out_pat = self.patterns_dir / f"{pat}.txt"
                        if out_pat.is_file():
                            out_pat.unlink()
                        pattern_results[pat] = 0
                except Exception:
                    pattern_results[pat] = 0
        else:
            # Fallback regex ligero si gf no está instalado
            patterns_regex = {
                "xss": re.compile(r"[?&](?:q|s|search|query|msg|message|name|comment|text)=", re.I),
                "sqli": re.compile(r"[?&](?:id|select|user_id|item|category|order|sort)=", re.I),
                "ssrf": re.compile(r"[?&](?:url|uri|target|dest|domain|host|endpoint|src)=", re.I),
                "redirect": re.compile(r"[?&](?:return|redirect|next|url|target|go)=", re.I),
                "idor": re.compile(r"[?&](?:account|user|profile|doc|file|invoice|order_id)=", re.I),
            }
            for pat, rx in patterns_regex.items():
                matches = [u for u in all_urls if rx.search(u)]
                pattern_results[pat] = len(matches)
                if matches and not self.dry_run:
                    out_pat = self.patterns_dir / f"{pat}.txt"
                    out_pat.write_text("\n".join(matches) + "\n", encoding="utf-8")

        return {
            "stage": "patterns",
            "patterns": pattern_results,
        }

    def generate_summary(self, stage_results: Dict[str, Any]) -> Dict[str, Any]:
        """Genera y guarda recon/summary.json."""
        summary: Dict[str, Any] = {
            "engagement": self.engagement_dir.name,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "in_scope_domains": self.get_in_scope_domains(),
            "stages_executed": list(stage_results.keys()),
            "subdomains_count": 0,
            "subdomains_discarded_out_of_scope": 0,
            "live_hosts_count": 0,
            "urls_count": 0,
            "js_files_count": 0,
            "gf_patterns": {},
            "tools_available": {k: bool(v) for k, v in self.tools.items()},
        }

        # Subdomains
        sub_file = self.recon_dir / "subdomains.txt"
        if sub_file.is_file():
            summary["subdomains_count"] = len([l for l in sub_file.read_text(encoding="utf-8").splitlines() if l.strip()])

        discarded_file = self.recon_dir / "out_of_scope_discarded.txt"
        if discarded_file.is_file():
            summary["subdomains_discarded_out_of_scope"] = len(
                [l for l in discarded_file.read_text(encoding="utf-8").splitlines() if l.strip()]
            )

        # Live hosts
        live_file = self.recon_dir / "live_hosts.txt"
        if live_file.is_file():
            summary["live_hosts_count"] = len([l for l in live_file.read_text(encoding="utf-8").splitlines() if l.strip()])

        # URLs y JS
        urls_file = self.recon_dir / "urls_all.txt"
        if urls_file.is_file():
            summary["urls_count"] = len([l for l in urls_file.read_text(encoding="utf-8").splitlines() if l.strip()])

        js_file = self.recon_dir / "js_files.txt"
        if js_file.is_file():
            summary["js_files_count"] = len([l for l in js_file.read_text(encoding="utf-8").splitlines() if l.strip()])

        # Patrones
        if self.patterns_dir.is_dir():
            for p in self.patterns_dir.glob("*.txt"):
                cnt = len([l for l in p.read_text(encoding="utf-8").splitlines() if l.strip()])
                summary["gf_patterns"][p.stem] = cnt

        if not self.dry_run:
            summary_path = self.recon_dir / "summary.json"
            summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        return summary

    def run_all(self, stage: str = "all") -> Dict[str, Any]:
        """Ejecuta el pipeline completo o una etapa específica."""
        self.prepare_directories()
        results: Dict[str, Any] = {}

        if stage in ("all", "subdomains"):
            results["subdomains"] = self.run_subdomain_enumeration()

        if stage in ("all", "probe"):
            results["probe"] = self.run_live_probing()

        if stage in ("all", "urls"):
            results["urls"] = self.run_url_harvesting()

        if stage in ("all", "patterns"):
            results["patterns"] = self.run_pattern_classification()

        summary = self.generate_summary(results)

        # Auditoría
        mark_msg = (
            f"RECON PIPELINE: {summary['subdomains_count']} subdominios autorizados "
            f"({summary['subdomains_discarded_out_of_scope']} descartados por scope), "
            f"{summary['live_hosts_count']} servicios web vivos, {summary['urls_count']} URLs analizadas"
        )
        record_audit_mark(self.engagement_dir, mark_msg)

        return {
            "summary": summary,
            "stage_results": results,
            "dry_run": self.dry_run,
        }


def cmd_run(args: argparse.Namespace) -> int:
    """Ejecuta el pipeline de reconocimiento."""
    eng_dir = resolve_engagement_dir(args.target)
    if not eng_dir:
        sys.stderr.write(f"Error: No se pudo localizar el directorio del engagement: {args.target or 'actual'}\n")
        return 1

    pipeline = ReconPipeline(eng_dir, dry_run=args.dry_run)
    res = pipeline.run_all(stage=args.stage)

    if args.json:
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return 0

    summary = res["summary"]
    prefix = "[DRY-RUN] " if args.dry_run else ""
    print(f"\n{prefix}SECLAB Recon Pipeline completado para: {eng_dir.name}")
    print(f"  Directorio: {pipeline.recon_dir}")
    print(f"  Dominios base autorizados: {', '.join(summary['in_scope_domains']) or 'ninguno'}")
    print(f"  Subdominios autorizados:   {summary['subdomains_count']}")
    if summary['subdomains_discarded_out_of_scope'] > 0:
        print(f"  Descartados por Scope:     {summary['subdomains_discarded_out_of_scope']} (guardados en out_of_scope_discarded.txt)")
    print(f"  Servicios web vivos:       {summary['live_hosts_count']}")
    print(f"  URLs recolectadas:         {summary['urls_count']} (Archivos JS: {summary['js_files_count']})")

    if summary["gf_patterns"]:
        pats = [f"{k}={v}" for k, v in summary["gf_patterns"].items() if v > 0]
        if pats:
            print(f"  Patrones gf detectados:    {', '.join(pats)}")

    print(f"  Resumen estructurado:      {pipeline.recon_dir / 'summary.json'}\n")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Muestra el estado del reconocimiento de un engagement."""
    eng_dir = resolve_engagement_dir(args.target)
    if not eng_dir:
        sys.stderr.write(f"Error: No se pudo localizar el engagement: {args.target or 'actual'}\n")
        return 1

    pipeline = ReconPipeline(eng_dir)
    summary_path = pipeline.recon_dir / "summary.json"
    if not summary_path.is_file():
        summary = pipeline.generate_summary({})
    else:
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except Exception:
            summary = pipeline.generate_summary({})

    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0

    print(f"\nEstado de Reconocimiento: {eng_dir.name}")
    print(f"  Ultima actualizacion:     {summary.get('timestamp', 'N/A')}")
    print(f"  Dominios en alcance:      {', '.join(summary.get('in_scope_domains', [])) or 'N/A'}")
    print(f"  Subdominios identificados: {summary.get('subdomains_count', 0)}")
    print(f"  Descartados (Scope Guard): {summary.get('subdomains_discarded_out_of_scope', 0)}")
    print(f"  Servicios web activos:    {summary.get('live_hosts_count', 0)}")
    print(f"  URLs archivadas:          {summary.get('urls_count', 0)}")
    print(f"  JavaScript descubiertos:  {summary.get('js_files_count', 0)}")
    if summary.get("gf_patterns"):
        pats = [f"{k}={v}" for k, v in summary["gf_patterns"].items() if v > 0]
        if pats:
            print(f"  Patrones de riesgo gf:    {', '.join(pats)}")
    print()
    return 0


def cmd_filter(args: argparse.Namespace) -> int:
    """Filtra una lista de objetivos contra las reglas de un engagement o target.yaml."""
    input_path = pathlib.Path(args.input_file)
    if not input_path.is_file():
        sys.stderr.write(f"Error: Archivo de entrada no encontrado: {args.input_file}\n")
        return 1

    target_cfg = pathlib.Path(args.target_config)
    if target_cfg.is_dir():
        scope_data = load_scope_rules(target_cfg)
    elif target_cfg.is_file():
        scope_data = load_scope_rules(target_cfg.parent)
    else:
        sys.stderr.write(f"Error: No se pudo resolver la configuracion de alcance: {args.target_config}\n")
        return 1

    in_scope_targets = []
    discarded = []

    for line in input_path.read_text(encoding="utf-8").splitlines():
        item = line.strip()
        if not item:
            continue
        verdict, reason = check_scope(item, scope_data)
        if verdict == "IN_SCOPE":
            in_scope_targets.append(item)
        else:
            discarded.append(f"{item} -> {verdict}: {reason}")

    if args.output:
        out_p = pathlib.Path(args.output)
        out_p.write_text("\n".join(in_scope_targets) + ("\n" if in_scope_targets else ""), encoding="utf-8")
        print(f"[+] {len(in_scope_targets)} objetivos en alcance guardados en {args.output}")
        if discarded:
            print(f"[!] {len(discarded)} objetivos descartados por estar fuera de alcance.")
    else:
        for t in in_scope_targets:
            print(t)

    return 0


def build_parser() -> argparse.ArgumentParser:
    """Construye el parser CLI para pt-recon-pipeline."""
    parser = argparse.ArgumentParser(
        prog="pt-recon-pipeline",
        description="Pipeline Automatizado de Reconocimiento con Scope Guard para SecLab-SBF.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcomando: run
    p_run = subparsers.add_parser("run", help="Ejecuta el pipeline de reconocimiento hacia un engagement.")
    p_run.add_argument("target", nargs="?", default=None, help="Nombre del engagement o directorio de trabajo.")
    p_run.add_argument(
        "--stage",
        choices=["all", "subdomains", "probe", "urls", "patterns"],
        default="all",
        help="Etapa específica a ejecutar (por defecto: all).",
    )
    p_run.add_argument("--dry-run", action="store_true", help="Simula la ejecución sin emitir tráfico de red.")
    p_run.add_argument("-j", "--json", action="store_true", help="Salida en formato JSON estructurado.")
    p_run.set_defaults(func=cmd_run)

    # Subcomando: status
    p_status = subparsers.add_parser("status", help="Muestra métricas del reconocimiento activo.")
    p_status.add_argument("target", nargs="?", default=None, help="Nombre del engagement o directorio.")
    p_status.add_argument("-j", "--json", action="store_true", help="Salida en formato JSON estructurado.")
    p_status.set_defaults(func=cmd_status)

    # Subcomando: filter
    p_filter = subparsers.add_parser("filter", help="Filtra una lista de dominios/URLs según el target.yaml.")
    p_filter.add_argument("input_file", help="Archivo con lista de dominios o URLs.")
    p_filter.add_argument("target_config", help="Ruta a target.yaml o al directorio del engagement.")
    p_filter.add_argument("-o", "--output", help="Archivo donde escribir los objetivos autorizados.")
    p_filter.set_defaults(func=cmd_filter)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
