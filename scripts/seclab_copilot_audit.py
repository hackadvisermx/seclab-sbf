#!/usr/bin/env python3
"""seclab_copilot_audit.py - Registro y verificación inmutable de consentimiento del Copiloto Táctico."""

from __future__ import annotations

import datetime
import hashlib
import json
import pathlib
from typing import Any, Dict, List, Optional


def log_copilot_consent(
    evidence_dir: pathlib.Path | str,
    engagement_id: str,
    agent_id: str,
    provider: str,
    model: str,
    network_tier: str,
    prompt_hash: str,
    context_hash: str,
    context_bytes: int,
    token: str,
) -> Dict[str, Any]:
    """Registra de forma inmutable una entrada de consentimiento en evidence/.copilot_consent.jsonl."""
    dir_path = pathlib.Path(evidence_dir)
    dir_path.mkdir(parents=True, exist_ok=True)
    consent_file = dir_path / ".copilot_consent.jsonl"

    record = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "engagement_id": str(engagement_id),
        "agent_id": str(agent_id),
        "provider": str(provider),
        "model": str(model),
        "network_tier": str(network_tier),
        "prompt_hash": str(prompt_hash),
        "context_hash": str(context_hash),
        "context_bytes": int(context_bytes),
        "token": str(token),
        "status": "consented",
    }

    with open(consent_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return record


def read_copilot_consent_history(
    evidence_dir: pathlib.Path | str,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Lee el historial cronológico inverso de consentimientos registrados."""
    dir_path = pathlib.Path(evidence_dir)
    consent_file = dir_path / ".copilot_consent.jsonl"
    if not consent_file.is_file():
        return []

    records = []
    with open(consent_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                if isinstance(record, dict) and "timestamp" in record and "status" in record:
                    records.append(record)
            except Exception:
                continue

    records.reverse()
    return records[:limit]
