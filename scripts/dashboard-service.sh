#!/bin/bash
# ==============================================================================
# SecLab SBF: Servicio Interno del Dashboard Táctico y API Key Vault
# ==============================================================================
set -euo pipefail

DASHBOARD_PORT="${DASHBOARD_PORT:-8080}"
DASHBOARD_HOST="${DASHBOARD_HOST:-0.0.0.0}"
WORKSPACE_DIR="${WORKSPACE_DIR:-/workspace}"
STATE_DIR="${STATE_DIR:-/var/lib/seclab/dashboard}"

# Asegurar directorio de datos para SQLite y claves
mkdir -p "$STATE_DIR"
chmod 700 "$STATE_DIR"

export WORKSPACE_DIR
export DASHBOARD_DIR="/usr/local/share/seclab/dashboard"
export SECLAB_DATA_DIR="$STATE_DIR"
export PYTHONPATH="/usr/local/share/seclab/dashboard/backend:${PYTHONPATH:-}"

exec /opt/nxc/bin/python3 -m uvicorn app.main:app \
    --app-dir /usr/local/share/seclab/dashboard/backend \
    --host "$DASHBOARD_HOST" \
    --port "$DASHBOARD_PORT"
