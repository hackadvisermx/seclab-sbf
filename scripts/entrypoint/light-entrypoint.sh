#!/bin/bash
set -Eeuo pipefail

ENV_FILE="${ENV_FILE_PATH:-/run/secrets/lab.env}"

if [[ ! -r "$ENV_FILE" ]]; then
  printf 'secret file is not readable: %s\n' "$ENV_FILE" >&2
  exit 78
fi

read_value() {
  local key="$1"
  local line
  local value=""
  while IFS= read -r line || [[ -n "$line" ]]; do
    if [[ "$line" == "$key="* ]]; then
      value="${line#*=}"
      value="${value%$'\r'}"
      break
    fi
  done < "$ENV_FILE"
  printf '%s' "$value"
}

require_value() {
  local name="$1"
  local value="$2"
  if [[ -z "$value" ]]; then
    printf '%s is required in %s\n' "$name" "$ENV_FILE" >&2
    exit 78
  fi
}

TTYD_USER="$(read_value TTYD_USER)"
TTYD_PASSWORD="$(read_value TTYD_PASSWORD)"
TTYD_INTERFACE="$(read_value TTYD_INTERFACE)"
TTYD_PORT="$(read_value TTYD_PORT)"
SSH_USER="$(read_value SSH_USER)"
SSH_PUBLIC_KEY="$(read_value SSH_PUBLIC_KEY)"
PENTEST_PROFILE="$(read_value PENTEST_PROFILE)"

TTYD_INTERFACE="${TTYD_INTERFACE:-0.0.0.0}"
TTYD_PORT="${TTYD_PORT:-7681}"
PENTEST_PROFILE="${PENTEST_PROFILE:-light}"

require_value TTYD_USER "$TTYD_USER"
require_value TTYD_PASSWORD "$TTYD_PASSWORD"
require_value SSH_USER "$SSH_USER"
require_value SSH_PUBLIC_KEY "$SSH_PUBLIC_KEY"

if [[ "$PENTEST_PROFILE" != "light" && "$PENTEST_PROFILE" != "full" ]]; then
  printf 'PENTEST_PROFILE must be light or full\n' >&2
  exit 64
fi

if [[ "$SSH_USER" != "tester" || "$TTYD_USER" != "tester" ]]; then
  printf 'SSH_USER and TTYD_USER must both be tester\n' >&2
  exit 64
fi

case "$SSH_PUBLIC_KEY" in
  ssh-*|ecdsa-*|sk-*) ;;
  *)
    printf 'SSH_PUBLIC_KEY is not a supported public key\n' >&2
    exit 65
    ;;
esac

if [[ ! -d /workspace || ! -w /workspace ]]; then
  printf 'workspace is not writable: /workspace\n' >&2
  exit 1
fi

id "$SSH_USER" >/dev/null

install -d -m 0700 -o "$SSH_USER" -g "$SSH_USER" \
  /var/lib/seclab/tester \
  /var/lib/seclab/tester/oh-my-zsh-cache \
  /var/lib/seclab/tester/zoxide

install -d -m 0755 /run/sshd
install -d -m 0755 -o root -g root /run/ssh
install -d -m 0755 -o root -g root /run/ssh/authorized_keys
install -d -m 0700 -o root -g root /var/lib/seclab/ssh
chown -R root:root /var/lib/seclab/ssh

printf '%s\n' "$SSH_PUBLIC_KEY" > "/run/ssh/authorized_keys/$SSH_USER"
chown "$SSH_USER:$SSH_USER" "/run/ssh/authorized_keys/$SSH_USER"
chmod 0600 "/run/ssh/authorized_keys/$SSH_USER"

if [[ ! -s /var/lib/seclab/ssh/ssh_host_ed25519_key ]]; then
  ssh-keygen -q -t ed25519 -N '' -f /var/lib/seclab/ssh/ssh_host_ed25519_key
fi
chmod 0600 /var/lib/seclab/ssh/ssh_host_ed25519_key
chmod 0644 /var/lib/seclab/ssh/ssh_host_ed25519_key.pub

/usr/sbin/sshd -t -f /etc/ssh/sshd_config.seclab

sshd_pid=""
ttyd_pid=""
cleanup() {
  set +e
  if [[ -n "$ttyd_pid" ]]; then kill "$ttyd_pid" 2>/dev/null; fi
  if [[ -n "$sshd_pid" ]]; then kill "$sshd_pid" 2>/dev/null; fi
  wait "$ttyd_pid" 2>/dev/null
  wait "$sshd_pid" 2>/dev/null
}
trap cleanup EXIT
trap 'exit 143' INT TERM

/usr/sbin/sshd -D -e -f /etc/ssh/sshd_config.seclab &
sshd_pid=$!
printf '%s\n' "$sshd_pid" > /run/ssh/sshd.pid

TTYD_USER="$TTYD_USER" TTYD_PASSWORD="$TTYD_PASSWORD" TTYD_INTERFACE="$TTYD_INTERFACE" TTYD_PORT="$TTYD_PORT" su -m -s /bin/bash "$SSH_USER" -c /usr/local/bin/ttyd-as-tester &
ttyd_pid=$!
printf '%s\n' "$ttyd_pid" > /run/ttyd.pid

set +e
wait -n "$sshd_pid" "$ttyd_pid"
status=$?
set -e
exit "$status"
