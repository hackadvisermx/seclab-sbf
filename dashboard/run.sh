#!/usr/bin/env bash
# ==============================================================================
# SecLab Tactical Dashboard & API Vault Launcher
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

DASHBOARD_PORT="${DASHBOARD_PORT:-8080}"
DASHBOARD_HOST="${DASHBOARD_HOST:-0.0.0.0}"
VENV_DIR="$SCRIPT_DIR/.venv"
PID_FILE="$SCRIPT_DIR/dashboard.pid"
LOG_FILE="$SCRIPT_DIR/backend/data/dashboard.log"

ACTION="${1:-start}"

mkdir -p "$SCRIPT_DIR/backend/data"

case "$ACTION" in
    stop|--stop)
        if [[ -f "$PID_FILE" ]]; then
            PID="$(cat "$PID_FILE" 2>/dev/null || true)"
            if [[ -n "$PID" ]] && kill -0 "$PID" 2>/dev/null; then
                kill "$PID" 2>/dev/null || true
                printf 'Dashboard detenido (PID %s).\n' "$PID"
            fi
            rm -f "$PID_FILE"
        fi
        if command -v lsof >/dev/null 2>&1; then
            PORT_PIDS="$(lsof -ti :"$DASHBOARD_PORT" 2>/dev/null || true)"
            if [[ -n "$PORT_PIDS" ]]; then
                kill $PORT_PIDS 2>/dev/null || true
            fi
        fi
        printf 'Dashboard detenido con éxito.\n'
        exit 0
        ;;
    status|--status)
        if [[ -f "$PID_FILE" ]]; then
            PID="$(cat "$PID_FILE" 2>/dev/null || true)"
            if [[ -n "$PID" ]] && kill -0 "$PID" 2>/dev/null; then
                printf 'Dashboard: ACTIVO (PID %s, Puerto %s)\n' "$PID" "$DASHBOARD_PORT"
                exit 0
            fi
        fi
        if command -v lsof >/dev/null 2>&1; then
            PORT_PIDS="$(lsof -ti :"$DASHBOARD_PORT" 2>/dev/null || true)"
            if [[ -n "$PORT_PIDS" ]]; then
                printf 'Dashboard: ACTIVO (Puerto %s)\n' "$DASHBOARD_PORT"
                exit 0
            fi
        fi
        printf 'Dashboard: DETENIDO\n'
        exit 0
        ;;
    daemon|--daemon)
        if [[ -f "$PID_FILE" ]]; then
            PID="$(cat "$PID_FILE" 2>/dev/null || true)"
            if [[ -n "$PID" ]] && kill -0 "$PID" 2>/dev/null; then
                printf 'El dashboard ya está corriendo en segundo plano (PID %s).\n' "$PID"
                exit 0
            fi
        fi
        if command -v lsof >/dev/null 2>&1; then
            STALE_PIDS="$(lsof -ti :"$DASHBOARD_PORT" 2>/dev/null || true)"
            if [[ -n "$STALE_PIDS" ]]; then
                kill $STALE_PIDS 2>/dev/null || true
                sleep 0.5
            fi
        fi
        export PYTHONUNBUFFERED=1
        nohup "$SCRIPT_DIR/run.sh" start </dev/null >> "$LOG_FILE" 2>&1 &
        NEW_PID=$!
        echo "$NEW_PID" > "$PID_FILE"
        disown "$NEW_PID" 2>/dev/null || true
        printf 'Dashboard iniciado en segundo plano (PID %s).\n' "$NEW_PID"
        printf 'Logs: %s\n' "$LOG_FILE"
        printf 'Acceso local: http://127.0.0.1:%s\n' "$DASHBOARD_PORT"
        exit 0
        ;;
    start|--start)
        ;;
    *)
        printf 'Uso: %s [start|daemon|stop|status]\n' "$0" >&2
        exit 1
        ;;
esac

# 1. Asegurar entorno virtual y dependencias
if [[ ! -d "$VENV_DIR" ]]; then
    printf '[+] Creando entorno virtual en %s...\n' "$VENV_DIR"
    python3 -m venv "$VENV_DIR"
    "$VENV_DIR/bin/pip" install --upgrade pip
    "$VENV_DIR/bin/pip" install -r "$SCRIPT_DIR/backend/requirements.txt"
fi

# 2. Comprobar si el frontend compilado existe
if [[ ! -d "$SCRIPT_DIR/frontend/dist" ]]; then
    if command -v npm >/dev/null 2>&1; then
        printf '[+] Compilando frontend Vue 3 en %s...\n' "$SCRIPT_DIR/frontend"
        (cd "$SCRIPT_DIR/frontend" && npm install && npm run build)
    else
        printf '[!] Advertencia: npm no disponible. FastAPI servirá la vista de respaldo.\n'
    fi
fi

# 3. Asegurar puertos loopback para ttyd (7681) y SSH (2222) si docker está activo
if command -v docker >/dev/null 2>&1; then
    if docker ps --format '{{.Names}}' 2>/dev/null | grep -q 'seclab-sbf-lab-1'; then
        if ! curl -s -I -m 1 http://127.0.0.1:7681 >/dev/null 2>&1; then
            printf '[+] Habilitando puertos loopback para ttyd (7681) y SSH (2222)...\n'
            mkdir -p "$REPO_ROOT/tmp"
            printf 'services:\n  lab:\n    ports:\n      - "127.0.0.1:2222:2222"\n      - "127.0.0.1:7681:7681"\n' > "$REPO_ROOT/tmp/compose.ssh.yaml"
            (cd "$REPO_ROOT" && docker compose -f compose.yaml -f compose.local.yaml -f tmp/compose.ssh.yaml up -d lab >/dev/null 2>&1 || true)
        fi
    fi
fi

# 4. Lanzar servidor uvicorn
printf '\n\033[36m==================================================================\033[0m\n'
printf '\033[36m⚡ SECLAB TACTICAL DASHBOARD & API KEY VAULT\033[0m\n'
printf '   Puerto:      http://%s:%s\n' "$DASHBOARD_HOST" "$DASHBOARD_PORT"
printf '   Terminal:    http://localhost:7681\n'
printf '   Workspace:   %s\n' "${WORKSPACE_DIR:-$REPO_ROOT/workspace}"
printf '\033[36m==================================================================\033[0m\n\n'

export PYTHONPATH="$SCRIPT_DIR/backend"
exec "$VENV_DIR/bin/python3" -m uvicorn app.main:app \
    --host "$DASHBOARD_HOST" \
    --port "$DASHBOARD_PORT"
