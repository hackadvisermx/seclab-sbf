#!/bin/sh
# Imprime la IP de la interfaz VPN para la barra de estado de tmux.
# Sin tun0 activa no imprime nada, para no dejar hueco en status-right.
# Usa rutas absolutas: el servidor tmux no hereda un PATH util.
set -eu

TUN_INTERFACE="${VPN_TUN_INTERFACE:-tun0}"

for ip_bin in /usr/sbin/ip /sbin/ip /bin/ip; do
  [ -x "$ip_bin" ] && break
  ip_bin=""
done

if [ -z "$ip_bin" ]; then
  exit 0
fi

"$ip_bin" -4 -o addr show dev "$TUN_INTERFACE" 2>/dev/null |
  awk '{ split($4, a, "/"); print a[1]; exit }' |
  while read -r address; do
    [ -n "$address" ] || continue
    printf 'vpn %s' "$address"
  done
