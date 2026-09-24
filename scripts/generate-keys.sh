#!/bin/sh
set -eu

project_root="$(CDPATH='' cd "$(dirname "$0")/.." && pwd)"
env_file="${SECLAB_ENV_FILE:-$project_root/.env}"
key_dir="${SECLAB_KEY_DIR:-$project_root/.secrets/ssh}"
private_key="$key_dir/seclab_ed25519"
public_key="$private_key.pub"

case "$env_file" in
  /*) ;;
  *) env_file="$project_root/$env_file" ;;
esac

if [ ! -e "$env_file" ]; then
  : > "$env_file"
fi
chmod 0600 "$env_file"

read_env_value() {
  awk -F= -v wanted="$1" '$1 == wanted { sub(/^[^=]*=/, ""); print; exit }' "$env_file"
}

write_env_value() {
  key="$1"
  value="$2"
  temporary="${env_file}.tmp.$$"
  awk -F= -v key="$key" -v value="$value" '
    $1 == key { print key "=" value; found = 1; next }
    { print }
    END { if (!found) print key "=" value }
  ' "$env_file" > "$temporary"
  chmod 0600 "$temporary"
  mv "$temporary" "$env_file"
}

ssh_value="$(read_env_value SSH_PUBLIC_KEY)"

if [ -n "$ssh_value" ]; then
  public_value="$ssh_value"
  key_source=existing-env
else
  if [ -e "$private_key" ] || [ -e "$public_key" ]; then
    if [ ! -f "$private_key" ] || [ ! -f "$public_key" ]; then
      printf '%s\n' 'El par SSH local está incompleto; no se sobrescribirá ninguna clave.' >&2
      exit 65
    fi
  else
    command -v ssh-keygen >/dev/null 2>&1 || {
      printf '%s\n' 'ssh-keygen no está disponible.' >&2
      exit 69
    }
    mkdir -p "$key_dir"
    chmod 0700 "$key_dir"
    ssh-keygen -q -t ed25519 -N '' -C 'seclab-local' -f "$private_key" >/dev/null 2>&1
  fi
  chmod 0600 "$private_key"
  chmod 0644 "$public_key"
  public_value="$(awk '{ print; exit }' "$public_key")"
  key_source=generated
fi

write_env_value SSH_PUBLIC_KEY "$public_value"
printf 'ssh_keys=ready source=%s user=tester\n' "$key_source"
