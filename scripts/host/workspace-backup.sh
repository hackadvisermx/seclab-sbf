#!/bin/sh
set -eu

# Empaqueta y genera checksum SHA-256 del workspace local o del host.
#
# Uso: workspace-backup.sh [directorio_workspace] [directorio_destino]

ws_dir="${1:-${WORKSPACE_DIR:-./workspace}}"
dest_dir="${2:-${BACKUP_DEST:-./backups}}"

if [ ! -d "$ws_dir" ]; then
  printf '%s\n' "error: el workspace no existe en '$ws_dir'" >&2
  exit 1
fi

mkdir -p "$dest_dir"

timestamp=$(date +%Y%m%d-%H%M%S)
backup_name="workspace-$timestamp.tar.gz"
backup_path="$dest_dir/$backup_name"
checksum_path="$dest_dir/$backup_name.sha256"

printf '%s\n' "==> Empaquetando workspace: $ws_dir -> $backup_path"
tar -czf "$backup_path" -C "$ws_dir" .

# Generar checksum compatible con sha256sum y shasum
if command -v sha256sum >/dev/null 2>&1; then
  (cd "$dest_dir" && sha256sum "$backup_name" > "$backup_name.sha256")
elif command -v shasum >/dev/null 2>&1; then
  (cd "$dest_dir" && shasum -a 256 "$backup_name" > "$backup_name.sha256")
else
  printf '%s\n' "aviso: ni sha256sum ni shasum disponibles; no se genero archivo .sha256" >&2
fi

printf '%s\n' "workspace_backup=ok archivo=$backup_path"
if [ -f "$checksum_path" ]; then
  printf '%s\n' "checksum: $(cat "$checksum_path")"
fi

notify_script="$(dirname -- "$0")/notify.sh"
if [ -f "$notify_script" ]; then
  /bin/sh "$notify_script" "Backup Workspace" "Respaldo generado exitosamente: $backup_name" "info" >/dev/null 2>&1 || true
fi
