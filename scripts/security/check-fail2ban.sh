#!/bin/sh
set -eu

# Verifica fail2ban en el host. No aplica nada, no modifica reglas y no
# imprime IPs baneadas ni datos del tailnet. Fuera de Linux se omite,
# igual que check-isolation.sh y check-tailscale.sh.

jail="security/fail2ban/jail.d/seclab-sshd.conf"
deployed="/etc/fail2ban/jail.d/seclab-sshd.conf"

if [ "$(uname -s)" != "Linux" ]; then
  printf '%s\n' "fail2ban_check=skipped platform=$(uname -s)"
  exit 0
fi

if ! command -v fail2ban-client >/dev/null 2>&1; then
  printf '%s\n' 'fail2ban_check=unavailable command=fail2ban-client'
  exit 78
fi

if [ ! -r "$jail" ]; then
  printf '%s\n' "fail2ban_check=invalid-repo path=$jail"
  exit 78
fi

if [ "$(id -u)" -ne 0 ]; then
  printf '%s\n' 'fail2ban_check=requires-root'
  exit 77
fi

# La jail del repo es la fuente de verdad: si el host tiene otra, el
# operador esta protegiendo algo distinto de lo que cree.
if [ ! -r "$deployed" ]; then
  printf '%s\n' "fail2ban_check=missing-jail path=$deployed"
  exit 78
fi
if ! cmp -s "$jail" "$deployed"; then
  printf '%s\n' "fail2ban_check=drift path=$deployed"
  exit 78
fi

# fail2ban-client -t es el validador real de la configuracion: detecta
# claves desconocidas y backends inexistentes antes de que arranque.
if ! fail2ban-client -t >/dev/null 2>&1; then
  printf '%s\n' 'fail2ban_check=invalid-config'
  exit 78
fi

if ! systemctl is-active --quiet fail2ban; then
  printf '%s\n' 'fail2ban_check=inactive service=fail2ban'
  exit 78
fi

# Solo se lee el numero de baneados: `status sshd` tambien imprime la
# lista de IPs, que no debe salir por log.
banned="$(fail2ban-client status sshd 2>/dev/null | sed -n 's/^[[:space:]]*Currently banned:[[:space:]]*//p')"
if [ -z "$banned" ]; then
  printf '%s\n' 'fail2ban_check=inactive jail=sshd'
  exit 78
fi

printf '%s\n' "fail2ban_check=ok jail=sshd banned=$banned"
