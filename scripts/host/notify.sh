#!/bin/sh
set -eu

# Envía alertas ligeras mediante Webhook HTTP (Discord, Slack o webhook genérico).
# Si ALERT_WEBHOOK_URL no está configurada, imprime la alerta localmente y sale con 0
# para no romper procesos ni scripts en entornos donde no se requieran notificaciones.
#
# Uso: notify.sh <titulo> <mensaje> [nivel: info|warning|error] [webhook_url]

title="${1:-Alerta SecLab}"
message="${2:-}"
level="${3:-info}"
webhook="${4:-${ALERT_WEBHOOK_URL:-}}"

if [ -z "$message" ]; then
  printf '%s\n' "uso: $0 <titulo> <mensaje> [nivel: info|warning|error] [webhook_url]" >&2
  exit 2
fi

timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
hostname_str=$(hostname 2>/dev/null || printf 'seclab-host')

# Registro local en log
printf '[%s] [%s] %s: %s\n' "$timestamp" "$level" "$title" "$message"

if [ -z "$webhook" ]; then
  exit 0
fi

if ! command -v curl >/dev/null 2>&1; then
  printf '%s\n' "aviso: curl no disponible; no se envio el webhook" >&2
  exit 0
fi

# Formato JSON estándar compatible con Slack, Discord y receptores HTTP
payload=$(cat <<EOF
{
  "username": "SecLab Alert",
  "text": "*[${level}] ${title}* (${hostname_str})\n${message}",
  "content": "*[${level}] ${title}* (${hostname_str})\n${message}"
}
EOF
)

curl -sS -X POST \
  -H "Content-Type: application/json" \
  -d "$payload" \
  --max-time 10 \
  "$webhook" >/dev/null 2>&1 || {
    printf '%s\n' "aviso: fallo al enviar webhook de alerta a $webhook" >&2
    exit 0
}

printf '%s\n' "notify=ok"
