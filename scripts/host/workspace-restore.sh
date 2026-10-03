#!/bin/sh
set -eu

# Restaura un respaldo tar.gz en el workspace, verificando el checksum si existe.
#
# Uso: workspace-restore.sh [directorio_workspace] [archivo_backup] [force]

ws_dir="${1:-${WORKSPACE_DIR:-./workspace}}"
backup_file="${2:-${BACKUP:-}}"
force="${3:-${FORCE:-0}}"

if [ -z "$backup_file" ]; then
  printf '%s\n' "uso: $0 [directorio_workspace] <archivo_backup> [force=1]" >&2
  printf '%s\n' "ejemplo: make workspace-restore BACKUP=./backups/workspace-20261003-120000.tar.gz" >&2
  exit 2
fi

if [ ! -f "$backup_file" ]; then
  printf '%s\n' "error: archivo de respaldo no encontrado en '$backup_file'" >&2
  exit 1
fi

# Verificar checksum si existe fichero .sha256
backup_dir=$(dirname -- "$backup_file")
backup_name=$(basename -- "$backup_file")
checksum_file="$backup_dir/$backup_name.sha256"

if [ -f "$checksum_file" ]; then
  printf '%s\n' "==> Verificando checksum SHA-256 de $backup_name..."
  if command -v sha256sum >/dev/null 2>&1; then
    (cd "$backup_dir" && sha256sum -c "$backup_name.sha256") || {
      printf '%s\n' "error: el checksum SHA-256 no coincide" >&2
      exit 1
    }
  elif command -v shasum >/dev/null 2>&1; then
    (cd "$backup_dir" && shasum -a 256 -c "$backup_name.sha256") || {
      printf '%s\n' "error: el checksum SHA-256 no coincide" >&2
      exit 1
    }
  fi
fi

# Comprobar si el workspace ya tiene archivos y no se especifico FORCE=1
if [ -d "$ws_dir" ] && [ "$(find "$ws_dir" -mindepth 1 -print -quit 2>/dev/null)" ]; then
  if [ "$force" != "1" ]; then
    printf '%s\n' "aviso: el workspace '$ws_dir' ya contiene archivos." >&2
    printf '%s\n' "Para sobreescribir usa: make workspace-restore BACKUP='$backup_file' FORCE=1" >&2
    exit 1
  fi
fi

mkdir -p "$ws_dir"

printf '%s\n' "==> Restaurando $backup_file en $ws_dir..."
tar -xzf "$backup_file" -C "$ws_dir"

printf '%s\n' "workspace_restore=ok destino=$ws_dir"

notify_script="$(dirname -- "$0")/notify.sh"
if [ -f "$notify_script" ]; then
  /bin/sh "$notify_script" "Restore Workspace" "Restauración completada en $ws_dir desde $backup_name" "warning" >/dev/null 2>&1 || true
fi
