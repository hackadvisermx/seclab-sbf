#!/usr/bin/env python3
"""seclab_record_job.py - Registro e ingestión de ejecuciones CLI manuales en recon_jobs.db."""

from __future__ import annotations

import argparse
import datetime
import os
import pathlib
import sqlite3
import sys
import uuid
from typing import Any, Dict, Optional


def now_utc() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def record_external_recon_job(
    db_path: pathlib.Path | str,
    engagement_type: str,
    engagement_id: str,
    tool: str,
    stage: str = "probe",
    command: Optional[str] = None,
    status: str = "completed",
    notes: Optional[str] = None,
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Inserta una ejecución de herramienta externa en el historial de recon_jobs."""
    db_file = pathlib.Path(db_path)
    if not db_file.exists():
        db_file.parent.mkdir(parents=True, exist_ok=True)

    effective_run_id = run_id or uuid.uuid4().hex
    started_at = now_utc()
    finished_at = started_at
    error_msg = f"[{tool}] {command or notes or 'Ejecución CLI manual'}"

    conn = sqlite3.connect(db_file, timeout=5)
    try:
        with conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS recon_job_history (
                    engagement_type TEXT NOT NULL, engagement_id TEXT NOT NULL,
                    run_id TEXT NOT NULL, status TEXT NOT NULL, stage TEXT NOT NULL,
                    dry_run INTEGER NOT NULL, started_at TEXT NOT NULL,
                    finished_at TEXT, error TEXT, scope_revision TEXT,
                    origin TEXT NOT NULL, PRIMARY KEY (engagement_type, engagement_id, run_id))"""
            )
            conn.execute(
                """INSERT INTO recon_job_history
                   (engagement_type, engagement_id, run_id, status, stage, dry_run, started_at, finished_at, error, scope_revision, origin)
                   VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, NULL, 'cli-external')""",
                (
                    str(engagement_type),
                    str(engagement_id),
                    effective_run_id,
                    status.lower(),
                    stage.lower(),
                    started_at,
                    finished_at,
                    error_msg,
                ),
            )
    finally:
        conn.close()

    return {
        "engagement_type": engagement_type,
        "engagement_id": engagement_id,
        "run_id": effective_run_id,
        "status": status.lower(),
        "stage": stage.lower(),
        "origin": "cli-external",
        "tool": tool,
        "started_at": started_at,
        "finished_at": finished_at,
        "info": error_msg,
    }


def main():
    parser = argparse.ArgumentParser(description="Ingesta una ejecución de comando CLI externo a recon_jobs.db")
    parser.add_argument("--engagement", required=True, help="ID del engagement o reto")
    parser.add_argument("--type", default="engagement", choices=["engagement", "reto"], help="Tipo de proyecto")
    parser.add_argument("--tool", required=True, help="Nombre de la herramienta (ej. nmap, httpx, ffuf)")
    parser.add_argument("--stage", default="probe", choices=["subdomains", "probe", "urls", "patterns", "all"], help="Etapa de auditoría")
    parser.add_argument("--command", default="", help="Línea de comando ejecutada")
    parser.add_argument("--status", default="completed", choices=["completed", "failed"], help="Resultado de la ejecución")
    parser.add_argument("--notes", default="", help="Observaciones o notas adicionales")
    parser.add_argument("--db", default=None, help="Ruta hacia recon-jobs.db")

    args = parser.parse_args()

    default_db = pathlib.Path(os.environ.get("SECLAB_DATA_DIR", "/var/lib/seclab/dashboard")) / "recon-jobs.db"
    db_path = pathlib.Path(args.db) if args.db else default_db

    res = record_external_recon_job(
        db_path=db_path,
        engagement_type=args.type,
        engagement_id=args.engagement,
        tool=args.tool,
        stage=args.stage,
        command=args.command,
        status=args.status,
        notes=args.notes,
    )
    print(f"OK: Registrada corrida externa {res['run_id']} ({res['tool']}) en {db_path}")


if __name__ == "__main__":
    main()
