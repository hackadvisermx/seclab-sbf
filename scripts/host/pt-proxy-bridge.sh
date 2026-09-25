#!/bin/sh
# Puente host-only para consumir pt-forward/pt-socks/pt-web sin publicar puertos.
# Solo escucha en loopback del host por defecto; con BIND=<ip-tailscale>
# se ata a la IP Tailscale del host (tailnet, nunca internet) para
# exponer ttyd/ssh del contenedor a dispositivos del tailnet vía ACL.
# Reenvía al loopback del contenedor mediante `docker compose exec`.
# No usa `ports:`, `network_mode: host` ni Tailscale dentro del contenedor.
# El consumo con túnel (`ssh -L` sobre el tailnet) sigue disponible.
set -eu

BIND="${BIND:-127.0.0.1}"
SERVICE="${1:-}"
HOST_PORT="${2:-}"
CONTAINER_PORT="${3:-}"

usage() {
  printf '%s\n' "uso: $0 <tcp|socks|web> [host_port] [container_port]" >&2
  printf '%s\n' '  tcp   por defecto 18080 18080 (pt-forward TCP)' >&2
  printf '%s\n' '  socks por defecto 1080 1080 (pt-socks SOCKS5)' >&2
  printf '%s\n' '  web   por defecto 18081 18081 (pt-web HTTP/HTTPS/WebSocket)' >&2
  printf '%s\n' 'ejemplo host: ./scripts/host/pt-proxy-bridge.sh tcp 18080 18080' >&2
  printf '%s\n' 'ejemplo laptop: ssh -L 18080:127.0.0.1:18080 usuario@<tailnet-host>' >&2
}

case "$SERVICE" in
  tcp) HOST_PORT="${HOST_PORT:-18080}"; CONTAINER_PORT="${CONTAINER_PORT:-18080}" ;;
  socks) HOST_PORT="${HOST_PORT:-1080}"; CONTAINER_PORT="${CONTAINER_PORT:-1080}" ;;
  web) HOST_PORT="${HOST_PORT:-18081}"; CONTAINER_PORT="${CONTAINER_PORT:-18081}" ;;
  *) usage; exit 2 ;;
esac

case "$HOST_PORT" in
  ''|*[!0-9]*)
    printf '%s\n' "puerto host invalido: $HOST_PORT" >&2
    exit 2
    ;;
esac

case "$CONTAINER_PORT" in
  ''|*[!0-9]*)
    printf '%s\n' "puerto contenedor invalido: $CONTAINER_PORT" >&2
    exit 2
    ;;
esac

if [ "$HOST_PORT" -lt 1024 ] || [ "$HOST_PORT" -gt 65535 ] || [ "$CONTAINER_PORT" -lt 1 ] || [ "$CONTAINER_PORT" -gt 65535 ]; then
  printf '%s\n' "puertos fuera de rango: host=$HOST_PORT container=$CONTAINER_PORT" >&2
  exit 2
fi

if ! command -v socat >/dev/null 2>&1; then
  printf '%s\n' 'se requiere socat en el host' >&2
  exit 78
fi

if ! command -v docker >/dev/null 2>&1; then
  printf '%s\n' 'se requiere docker en el host' >&2
  exit 78
fi

printf '%s\n' "bridge=${BIND}:${HOST_PORT} -> container=127.0.0.1:${CONTAINER_PORT} service=${SERVICE}"
printf '%s\n' 'el proxy del contenedor sigue validando tun0; este puente no abre puertos publicos'

# Cada conexion del host se transporta por stdio de `docker compose exec`
# hasta el listener loopback existente dentro del contenedor.
exec socat "TCP-LISTEN:${HOST_PORT},bind=${BIND},reuseaddr,fork" \
  "EXEC:docker compose -f compose.yaml -f compose.local.yaml exec -T --user 1000\\:1000 lab socat STDIO TCP\\:127.0.0.1\\:${CONTAINER_PORT}"
