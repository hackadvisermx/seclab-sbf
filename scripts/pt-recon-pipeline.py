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
import hashlib
import ipaddress
import json
import os
import pathlib
import re
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlsplit

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from seclab_scope import (ScopeError, normalize_target, is_ip, domain_matches,
                          parse_simple_yaml_lists, load_scope_rules, load_target_yaml, load_scope_txt, check_scope, authorization_contract, require_authorization)

from seclab_recon_probe import ProbeClient, operational_limits

DEFAULT_GF_PATTERNS = ["xss", "sqli", "ssrf", "redirect", "idor", "rce", "lfi"]


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


def send_notification(title: str, message: str, level: str = 'info') -> None:
    """Notificación opcional por webhook, apagada por defecto (reutiliza el patrón de
    scripts/host/notify.sh pero para uso dentro del contenedor). Sin SECLAB_NOTIFY_WEBHOOK
    no hace nada; con ella, un POST JSON compatible con Slack/Discord/webhook genérico.
    Nunca bloquea ni interrumpe al llamador: cualquier fallo de red o configuración
    se ignora en silencio, igual que notify.sh.
    """
    webhook = os.environ.get('SECLAB_NOTIFY_WEBHOOK', '').strip()
    if not webhook:
        return
    try:
        hostname = socket.gethostname()
    except OSError:
        hostname = 'seclab-lab'
    text = f'*[{level}] {title}* ({hostname})\n{message}'
    payload = json.dumps({'username': 'SecLab Alert', 'text': text, 'content': text}).encode('utf-8')
    request = urllib.request.Request(webhook, data=payload, headers={'Content-Type': 'application/json'}, method='POST')
    try:
        urllib.request.urlopen(request, timeout=10).close()
    except Exception:
        pass


class StageError(RuntimeError):
    pass


class ReconPipeline:
    def __init__(self, engagement_dir: pathlib.Path, dry_run: bool = False, live: bool = False):
        self.engagement_dir = engagement_dir.resolve()
        self.recon_dir = self.engagement_dir / "recon"
        self.patterns_dir = self.recon_dir / "patterns"
        self.dry_run = dry_run
        self.live = live and not dry_run
        self.progress = {'run_id': os.environ.get('SECLAB_RECON_RUN_ID'), 'stage': None,
                         'command': None, 'command_status': None, 'completed_stages': [],
                         'recent_output': [], 'events': []}
        self.scope_data = load_scope_rules(self.engagement_dir)
        self.limits = operational_limits(self.scope_data)
        self.scope_contract = self._contract(self.scope_data)
        self.scope_revision = self._revision(self.scope_contract)
        self.tools = detect_tools()

    @staticmethod
    def _contract(data):
        return {'scope': data['scope'], 'operational_limits': operational_limits(data),
                'authorization': authorization_contract(data)}

    @staticmethod
    def _revision(contract):
        return hashlib.sha256(json.dumps(contract, sort_keys=True, ensure_ascii=False,
                                        separators=(',', ':')).encode('utf-8')).hexdigest()

    def revalidate_scope(self, target=None):
        current = load_scope_rules(self.engagement_dir)
        if self._revision(self._contract(current)) != self.scope_revision:
            raise ScopeError('El alcance o sus límites cambiaron durante el reconocimiento; no se iniciarán nuevas acciones. Simula y ejecuta un plan nuevo.')
        if target is not None:
            require_authorization(current, 'active')
            verdict, reason = check_scope(target, current)
            if verdict != 'IN_SCOPE':
                raise ScopeError(f'Acción bloqueada por alcance para {target}: {verdict} ({reason}).')

    def prepare_directories(self):
        if not self.dry_run:
            self.recon_dir.mkdir(parents=True, exist_ok=True)
            self.patterns_dir.mkdir(parents=True, exist_ok=True)

    def get_in_scope_domains(self):
        return [value.strip() for value in self.scope_data['scope'].get('in_scope', {}).get('domains', [])]

    def filter_domains_by_scope(self, raw_targets):
        valid, discarded, seen = [], [], set()
        for raw in raw_targets:
            if not raw.strip():
                continue
            target = normalize_target(raw)
            key = target or raw.strip()
            if key in seen:
                continue
            seen.add(key)
            verdict, reason = check_scope(raw, self.scope_data)
            if verdict == 'IN_SCOPE':
                valid.append(target)
            else:
                discarded.append({'target': key, 'verdict': verdict, 'reason': reason,
                                  'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat()})
        return sorted(valid), discarded

    def _read_lines(self, name):
        path = self.recon_dir / name
        return [line.strip() for line in path.read_text(encoding='utf-8').splitlines() if line.strip()] if path.is_file() else []

    def _write_lines(self, name, lines):
        if not self.dry_run:
            path = self.recon_dir / name
            temporary = path.with_name(path.name + '.tmp')
            temporary.write_text(''.join(line + '\n' for line in lines), encoding='utf-8')
            temporary.replace(path)

    def _emit(self, event, **fields):
        if not self.live:
            return
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        if event == 'command_start':
            self.progress.update(recent_output=[], command_started_at=now)
        output = fields.pop('output', None)
        self.progress.update(fields, updated_at=now)
        if output is not None:
            lines = [line[:2000] for line in output.splitlines() if line.strip()]
            self.progress['recent_output'] = (self.progress['recent_output'] + lines)[-80:]
            for line in lines:
                print(line, flush=True)
        else:
            self.progress['events'] = (self.progress['events'] + [{'event': event, 'at': now, **fields}])[-32:]
            print(f"[RECON] {event}: " + str(fields.get('command') or fields.get('stage') or fields.get('status') or ''), flush=True)
        temporary = self.recon_dir / '.progress.json.tmp'
        temporary.write_text(json.dumps(self.progress, ensure_ascii=False), encoding='utf-8')
        temporary.replace(self.recon_dir / 'progress.json')

    def _stream_tool(self, command, timeout):
        with tempfile.NamedTemporaryFile(delete=False) as out, tempfile.NamedTemporaryFile(delete=False) as err:
            try:
                with open(out.name, 'rb') as output_reader, open(err.name, 'rb') as error_reader:
                    pathlib.Path(out.name).unlink()
                    pathlib.Path(err.name).unlink()
                    proc = subprocess.Popen(command, stdout=out, stderr=err)
                    deadline = time.monotonic() + timeout
                    try:
                        while True:
                            finished = proc.poll() is not None
                            for reader in (output_reader, error_reader):
                                chunk = reader.read()
                                if chunk:
                                    self._emit('output', output=chunk.decode('utf-8', errors='replace'))
                            if finished:
                                break
                            if time.monotonic() >= deadline:
                                raise subprocess.TimeoutExpired(command, timeout)
                            time.sleep(0.1)
                    finally:
                        if proc.poll() is None:
                            proc.kill()
                        proc.wait()
                    output_reader.seek(0)
                    error_reader.seek(0)
                    return subprocess.CompletedProcess(command, proc.returncode,
                        output_reader.read().decode('utf-8', errors='replace'), error_reader.read().decode('utf-8', errors='replace'))
            finally:
                pathlib.Path(out.name).unlink(missing_ok=True)
                pathlib.Path(err.name).unlink(missing_ok=True)

    def _tool(self, name, arguments, timeout=180):
        self.revalidate_scope()
        require_authorization(load_scope_rules(self.engagement_dir), 'passive')
        command = [self.tools[name], *arguments]
        self._emit('command_start', command=shlex.join(command), command_status='running')
        try:
            result = self._stream_tool(command, timeout) if self.live else subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
        except subprocess.TimeoutExpired:
            self._emit('command_end', command_status='failed')
            raise StageError(f'{name}: tiempo agotado; los resultados anteriores se conservan.') from None
        except OSError:
            self._emit('command_end', command_status='failed')
            raise StageError(f'{name}: no se pudo ejecutar; los resultados anteriores se conservan.') from None
        self._emit('command_end', command_status='completed' if result.returncode == 0 else 'failed', exit_code=result.returncode)
        if result.returncode != 0:
            if name == 'subfinder' and 'Could not create provider config file' in (result.stderr or ''):
                raise StageError('subfinder: no se pudo preparar provider-config.yaml; reconstruye la imagen con la configuración precargada. No se usan resultados parciales.')
            raise StageError(f'{name}: código de salida {result.returncode}; no se usan resultados parciales.')
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]

    def run_subdomain_enumeration(self):
        domains = self.get_in_scope_domains()
        seeds = self.scope_data['scope'].get('in_scope', {}).get('ips', [])
        previous = set(self._read_lines('subdomains.txt'))
        discovered = set(previous) | set(seeds)
        bases = sorted({domain[2:] if domain.startswith('*.') else domain for domain in domains})
        if self.dry_run:
            return {'stage': 'subdomains', 'status': 'simulated', 'planned_passive_queries': bases}
        if bases:
            require_authorization(load_scope_rules(self.engagement_dir), 'passive')
        available = [name for name in ('subfinder', 'assetfinder', 'findomain') if self.tools.get(name)]
        if bases and not available:
            raise StageError('No hay enumeradores pasivos disponibles; no se inventaron subdominios.')
        if not bases and not discovered:
            raise StageError('No hay dominios ni IPs explícitas. Para un CIDR, prepara una lista de IPs en recon/subdomains.txt.')
        for base in bases:
            if check_scope(base, self.scope_data)[0] == 'IN_SCOPE':
                discovered.add(base)
            for name in available:
                arguments = {'subfinder': ['-d', base, '-silent', '-rl', str(max(1, int(self.limits['max_requests_per_second'])))],
                             'assetfinder': ['--subs-only', base], 'findomain': ['-t', base, '-q']}[name]
                discovered.update(self._tool(name, arguments))
        valid, discarded = self.filter_domains_by_scope(sorted(discovered))
        new_subdomains = sorted(set(valid) - previous)
        self._write_lines('subdomains.txt', valid)
        self._write_lines('subdomains_new.txt', new_subdomains)
        self._write_lines('out_of_scope_discarded.txt', [f"[{row['timestamp']}] {row['target']} -> {row['verdict']}: {row['reason']}" for row in discarded])
        return {'stage': 'subdomains', 'status': 'completed', 'total_raw': len(discovered), 'in_scope_count': len(valid),
                'discarded_count': len(discarded), 'subdomains': valid, 'discarded': discarded,
                'new_count': len(new_subdomains)}

    def run_live_probing(self):
        if not (self.recon_dir / 'subdomains.txt').is_file():
            if self.dry_run:
                return {'stage': 'probe', 'status': 'simulated', 'planned_targets': []}
            raise StageError('No existe recon/subdomains.txt. Ejecuta primero subdomains o prepara una lista autorizada.')
        hosts, discarded = self.filter_domains_by_scope(self._read_lines('subdomains.txt'))
        if len(hosts) > self.limits['max_probe_targets']:
            raise StageError('Demasiados objetivos para max_probe_targets; no se inició el sondeo.')
        if self.dry_run:
            return {'stage': 'probe', 'status': 'simulated', 'planned_targets': hosts, 'discarded': discarded}
        if hosts:
            require_authorization(load_scope_rules(self.engagement_dir), 'active')
        previous_live = set(self._read_lines('live_hosts.txt'))
        self._emit('command_start', command=f'Sondeo HTTP interno: GET / por HTTP y HTTPS; {len(hosts)} hosts autorizados', command_status='running')
        self.revalidate_scope()
        client = ProbeClient(self.scope_data, self.limits, before_request=self.revalidate_scope)
        observations = client.probe(hosts, on_result=lambda rows: self._emit('output', output='\n'.join(
            f"{row.get('url', row.get('host'))}: {row['status']} {row.get('http_status', '')}" for row in rows))) if self.live else client.probe(hosts)
        self._emit('command_end', command_status='completed')
        live = sorted({row['url'] for row in observations if row['status'] == 'response'})
        new_live = sorted(set(live) - previous_live)
        self._write_lines('live_hosts.txt', live)
        self._write_lines('live_hosts_new.txt', new_live)
        self._write_lines('probe_observations.jsonl', [json.dumps(row, ensure_ascii=False) for row in observations])
        self._write_lines('probe_discarded.txt', [f"{row['target']} -> {row['verdict']}: {row['reason']}" for row in discarded])
        next_commands = self.generate_next_commands(live)
        self._write_lines('next_commands.txt', next_commands)
        return {'stage': 'probe', 'status': 'completed', 'live_hosts_count': len(live), 'live_hosts': live,
                'discarded_count': len(discarded), 'blocked_dns_count': sum(row['status'] == 'blocked' for row in observations),
                'operational_limits': self.limits, 'new_count': len(new_live),
                'next_commands_count': len(live)}

    def generate_next_commands(self, live_urls):
        """Sugiere, por cada host vivo, un comando pt-nmp y pt-fuzz-params listos para copiar.

        Inspirado en el _manual_commands.txt de AutoRecon: le da al operador novato
        el siguiente paso concreto sin que tenga que decidirlo desde cero. Usa los
        mismos binarios/helpers ya documentados (pentest-lab.plugin.zsh); no inventa
        hallazgos ni ejecuta nada por sí mismo.
        """
        lines = []
        for url in live_urls:
            host = urlsplit(url).hostname
            if not host:
                continue
            if lines:
                lines.append('')
            lines.append(f'# {url}')
            lines.append(f'pt-nmp {host}')
            lines.append(f'pt-fuzz-params "{url}"')
        return lines

    def run_url_harvesting(self):
        bases = sorted({domain[2:] if domain.startswith('*.') else domain for domain in self.get_in_scope_domains()})
        if self.dry_run:
            return {'stage': 'urls', 'status': 'simulated', 'planned_passive_queries': bases}
        if bases:
            require_authorization(load_scope_rules(self.engagement_dir), 'passive')
        available = [name for name in ('gau', 'waybackurls') if self.tools.get(name)]
        if bases and not available:
            raise StageError('No hay herramientas de URLs históricas; no se inventaron URLs.')
        raw = set()
        for base in bases:
            for name in available:
                arguments = ['--subs', '--threads', '1', '--timeout', '15', '--retries', '0', base] if name == 'gau' else [base]
                raw.update(self._tool(name, arguments))
        urls = sorted(url for url in raw if check_scope(url, self.scope_data)[0] == 'IN_SCOPE')
        javascript = [url for url in urls if re.search(r'\.js(\?|$)', url, re.I)]
        self._write_lines('urls_all.txt', urls)
        self._write_lines('js_files.txt', javascript)
        return {'stage': 'urls', 'status': 'completed', 'urls_count': len(urls), 'js_files_count': len(javascript)}

    def run_pattern_classification(self):
        if not (self.recon_dir / 'urls_all.txt').is_file():
            if self.dry_run:
                return {'stage': 'patterns', 'status': 'simulated'}
            raise StageError('No existe recon/urls_all.txt para clasificar patrones.')
        urls = [url for url in self._read_lines('urls_all.txt') if check_scope(url, self.scope_data)[0] == 'IN_SCOPE']
        if self.dry_run:
            return {'stage': 'patterns', 'status': 'simulated', 'planned_urls_count': len(urls)}
        if not self.tools.get('gf') and urls:
            raise StageError('gf no está disponible; no se generaron resultados de patrones.')
        results = {}
        temporary = self.recon_dir / '.pattern-input.txt'
        try:
            temporary.write_text(''.join(url + '\n' for url in urls), encoding='utf-8')
            outputs = {}
            for pattern in DEFAULT_GF_PATTERNS:
                matches = self._tool('gf', [pattern, str(temporary)], 60) if urls else []
                outputs[pattern] = sorted({value for value in matches if check_scope(value, self.scope_data)[0] == 'IN_SCOPE'})
            for pattern, matches in outputs.items():
                self._write_lines('patterns/' + pattern + '.txt', matches)
                results[pattern] = len(matches)
        finally:
            temporary.unlink(missing_ok=True)
        return {'stage': 'patterns', 'status': 'completed', 'patterns': results, 'classification_only': True}

    def generate_summary(self, results):
        failed = any(result.get('status') == 'failed' for result in results.values())
        resumable_from = next((name for name, result in results.items() if result.get('status') == 'failed'), None)
        failure = results.get(resumable_from, {})
        summary = {'engagement': self.engagement_dir.name,
                   'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   'in_scope_domains': self.get_in_scope_domains(), 'stages_executed': list(results),
                   'status': 'failed' if failed else 'simulated' if self.dry_run else 'completed',
                   'failure_kind': failure.get('failure_kind'), 'error': failure.get('error'),
                   'resumable_from': resumable_from,
                   'dry_run': self.dry_run, 'operational_limits': self.limits,
                   'run_id': self.progress['run_id'],
                   'scope_revision': self.scope_revision, 'scope_contract': self.scope_contract,
                   'stage_results': results, 'tools_available': {name: bool(path) for name, path in self.tools.items()},
                   'metrics_source': 'none' if self.dry_run else 'previous_artifacts' if failed else 'artifacts',
                   'subdomains_count': 0, 'subdomains_discarded_out_of_scope': 0, 'subdomains_new_count': 0,
                   'live_hosts_count': 0, 'live_hosts_new_count': 0, 'urls_count': 0, 'js_files_count': 0, 'gf_patterns': {}}
        if not self.dry_run:
            for key, filename in (('subdomains_count', 'subdomains.txt'), ('subdomains_discarded_out_of_scope', 'out_of_scope_discarded.txt'),
                                  ('subdomains_new_count', 'subdomains_new.txt'),
                                  ('live_hosts_count', 'live_hosts.txt'), ('live_hosts_new_count', 'live_hosts_new.txt'),
                                  ('urls_count', 'urls_all.txt'), ('js_files_count', 'js_files.txt')):
                summary[key] = len(self._read_lines(filename))
            if self.patterns_dir.is_dir():
                for path in self.patterns_dir.glob('*.txt'):
                    summary['gf_patterns'][path.stem] = len([line for line in path.read_text().splitlines() if line.strip()])
            self._write_lines('summary.json', [json.dumps(summary, indent=2, ensure_ascii=False)])
        return summary

    def _load_checkpoint(self):
        path = self.recon_dir / '.checkpoint.json'
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return None
        return data if isinstance(data.get('completed'), dict) else None

    def run_all(self, stage='all', resume=False):
        if stage not in ('all', 'subdomains', 'probe', 'urls', 'patterns'):
            raise ScopeError('Etapa de reconocimiento no válida.')
        self.prepare_directories()
        results = {}
        checkpoint_path = self.recon_dir / '.checkpoint.json'
        if stage == 'all' and resume and not self.dry_run:
            checkpoint = self._load_checkpoint()
            if checkpoint:
                if checkpoint.get('scope_revision') != self.scope_revision:
                    raise ScopeError('El checkpoint no corresponde al alcance actual. Simula y reinicia sin --resume; se conservan los artefactos anteriores.')
                results.update(checkpoint['completed'])
        elif stage != 'all' and not self.dry_run:
            # Una etapa manual rompe el orden que asume la cadena automática;
            # el checkpoint de "all" ya no es fiable para reanudar.
            checkpoint_path.unlink(missing_ok=True)
        failed_stage = None
        self.progress['completed_stages'] = list(results)
        self._emit('run_start', status='running', selected_stage=stage, total_stages=4 if stage == 'all' else 1)
        for name, action in (('subdomains', self.run_subdomain_enumeration), ('probe', self.run_live_probing),
                             ('urls', self.run_url_harvesting), ('patterns', self.run_pattern_classification)):
            if stage not in ('all', name):
                continue
            if name in results and results[name].get('status') != 'failed':
                continue
            self._emit('stage_start', stage=name, stage_status='running', command=None, command_status=None, recent_output=[])
            try:
                self.revalidate_scope()
                results[name] = action()
                results[name]['interaction'] = 'simulation' if self.dry_run else {'subdomains': 'passive', 'probe': 'active', 'urls': 'passive', 'patterns': 'local'}[name]
                self.progress['completed_stages'].append(name)
                self._emit('stage_end', stage=name, stage_status=results[name]['status'])
            except (StageError, ScopeError, OSError) as error:
                failure_kind = 'scope_guard' if isinstance(error, ScopeError) else 'technical'
                results[name] = {'stage': name, 'status': 'failed', 'error': str(error), 'failure_kind': failure_kind}
                failed_stage = name
                self._emit('stage_end', stage=name, stage_status='failed', error=str(error), failure_kind=failure_kind)
                break
        summary = self.generate_summary(results)
        self._emit('run_end', status=summary['status'])
        if stage == 'all' and not self.dry_run:
            if failed_stage:
                completed = {name: result for name, result in results.items() if result.get('status') != 'failed'}
                self._write_lines('.checkpoint.json', [json.dumps(
                    {'completed': completed, 'failed_stage': failed_stage, 'scope_revision': self.scope_revision,
                     'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat()},
                    ensure_ascii=False)])
            else:
                checkpoint_path.unlink(missing_ok=True)
        if not self.dry_run:
            record_audit_mark(self.engagement_dir, f"RECON PIPELINE: {summary['status']}; etapas: {', '.join(results)}")
            send_notification(
                f"Reconocimiento {summary['status']}: {self.engagement_dir.name}",
                f"Etapa: {stage} | Subdominios: {summary['subdomains_count']} | "
                f"Hosts vivos: {summary['live_hosts_count']} | URLs: {summary['urls_count']}",
                level='error' if summary['status'] == 'failed' else 'info',
            )
        return {'summary': summary, 'stage_results': results, 'dry_run': self.dry_run}


def retry_command(eng_dir, summary):
    options = '--resume' if (eng_dir / 'recon' / '.checkpoint.json').is_file() else '--stage ' + shlex.quote(summary['resumable_from'])
    return f'pt-recon {shlex.quote(str(eng_dir))} {options}'


def cmd_run(args: argparse.Namespace) -> int:
    """Ejecuta el pipeline de reconocimiento."""
    if args.resume and args.stage != 'all':
        sys.stderr.write("Error: --resume solo aplica a la cadena completa (--stage all, el valor por defecto).\n")
        return 1

    eng_dir = resolve_engagement_dir(args.target)
    if not eng_dir:
        sys.stderr.write(f"Error: No se pudo localizar el directorio del engagement: {args.target or 'actual'}\n")
        return 1

    try:
        pipeline = ReconPipeline(eng_dir, dry_run=args.dry_run, live=not args.json)
        res = pipeline.run_all(stage=args.stage, resume=args.resume)
    except (ScopeError, OSError) as error:
        sys.stderr.write(f"Error: {error}\n")
        return 1

    if args.json:
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return 1 if res["summary"]["status"] == "failed" else 0

    summary = res["summary"]
    prefix = "[DRY-RUN] " if args.dry_run else ""
    print(f"\n{prefix}SECLAB Recon Pipeline {summary['status']} para: {eng_dir.name}")
    print(f"  Directorio: {pipeline.recon_dir}")
    print(f"  Dominios base autorizados: {', '.join(summary['in_scope_domains']) or 'ninguno'}")
    subdomains_new = summary.get('subdomains_new_count', 0)
    print(f"  Subdominios autorizados:   {summary['subdomains_count']}" + (f" ({subdomains_new} nuevos desde la última corrida)" if subdomains_new else ""))
    if summary['subdomains_discarded_out_of_scope'] > 0:
        print(f"  Descartados por Scope:     {summary['subdomains_discarded_out_of_scope']} (guardados en out_of_scope_discarded.txt)")
    live_hosts_new = summary.get('live_hosts_new_count', 0)
    print(f"  Servicios web vivos:       {summary['live_hosts_count']}" + (f" ({live_hosts_new} nuevos desde la última corrida)" if live_hosts_new else ""))
    print(f"  URLs recolectadas:         {summary['urls_count']} (Archivos JS: {summary['js_files_count']})")

    if summary["gf_patterns"]:
        pats = [f"{k}={v}" for k, v in summary["gf_patterns"].items() if v > 0]
        if pats:
            print(f"  Patrones gf detectados:    {', '.join(pats)}")

    next_commands_count = res["stage_results"].get("probe", {}).get("next_commands_count", 0)
    if next_commands_count:
        print(f"  Próximos comandos sugeridos: {pipeline.recon_dir / 'next_commands.txt'} ({next_commands_count} hosts)")
    print(f"  Resumen estructurado:      {pipeline.recon_dir / 'summary.json'}\n")
    for result in res["stage_results"].values():
        if result.get("error"):
            print("  Error: " + result["error"])
    if summary.get("resumable_from") and not args.dry_run:
        print(f"  Para reintentar la etapa fallida: {retry_command(eng_dir, summary)}\n")
    return 1 if summary["status"] == "failed" else 0


def cmd_status(args: argparse.Namespace) -> int:
    """Muestra el estado del reconocimiento de un engagement."""
    eng_dir = resolve_engagement_dir(args.target)
    if not eng_dir:
        sys.stderr.write(f"Error: No se pudo localizar el engagement: {args.target or 'actual'}\n")
        return 1

    pipeline = ReconPipeline(eng_dir, dry_run=True)
    summary_path = pipeline.recon_dir / "summary.json"
    if not summary_path.is_file():
        summary = pipeline.generate_summary({})
        summary['status'] = 'not_run'
    else:
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except Exception:
            raise ScopeError('El resumen existente es inválido; no se ha reemplazado.') from None

    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0

    print(f"\nEstado de Reconocimiento: {eng_dir.name}")
    print(f"  Ultima actualizacion:     {summary.get('timestamp', 'N/A')}")
    print(f"  Dominios en alcance:      {', '.join(summary.get('in_scope_domains', [])) or 'N/A'}")
    status_subdomains_new = summary.get('subdomains_new_count', 0)
    print(f"  Subdominios identificados: {summary.get('subdomains_count', 0)}" + (f" ({status_subdomains_new} nuevos desde la última corrida)" if status_subdomains_new else ""))
    print(f"  Descartados (Scope Guard): {summary.get('subdomains_discarded_out_of_scope', 0)}")
    status_live_new = summary.get('live_hosts_new_count', 0)
    print(f"  Servicios web activos:    {summary.get('live_hosts_count', 0)}" + (f" ({status_live_new} nuevos desde la última corrida)" if status_live_new else ""))
    print(f"  URLs archivadas:          {summary.get('urls_count', 0)}")
    print(f"  JavaScript descubiertos:  {summary.get('js_files_count', 0)}")
    if summary.get("gf_patterns"):
        pats = [f"{k}={v}" for k, v in summary["gf_patterns"].items() if v > 0]
        if pats:
            print(f"  Patrones de riesgo gf:    {', '.join(pats)}")
    if summary.get("resumable_from"):
        print(f"  Pendiente de reintentar en: {summary['resumable_from']} ({retry_command(eng_dir, summary)})")
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
        scope_data = load_scope_txt(target_cfg) if target_cfg.suffix == '.txt' else load_target_yaml(target_cfg)
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
    p_run.add_argument(
        "--resume",
        action="store_true",
        help="Con --stage all (por defecto): omite las etapas que ya completaron en el intento anterior y continúa desde la que falló.",
    )
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
    try:
        return args.func(args)
    except (ScopeError, OSError) as error:
        sys.stderr.write(f'Error: {error}\n')
        return 1


if __name__ == "__main__":
    sys.exit(main())
