#!/bin/sh
set -eu

# Renderiza el cloud-init compartido y comprueba que sigue siendo YAML
# valido y que la jail de fail2ban llega al host identica al repo.
#
# `terraform validate` NO cubre esto: la plantilla se renderiza bien y
# validate pasa aunque el bloque `content: |` quede sin indentar, porque
# el YAML roto solo se ve al aplicar. Este script es el que habria
# avisado del fallo de indent() de la Fase 20.

template="terraform/modules/lab-cloud-init/cloud.cfg.yaml"
jail="security/fail2ban/jail.d/seclab-sshd.conf"
root="$(pwd)"

if ! command -v terraform >/dev/null 2>&1; then
  printf '%s\n' 'tf_render_check=unavailable command=terraform'
  exit 78
fi

if ! command -v python3 >/dev/null 2>&1; then
  printf '%s\n' 'tf_render_check=unavailable command=python3'
  exit 78
fi

if ! python3 -c 'import yaml' >/dev/null 2>&1; then
  printf '%s\n' 'tf_render_check=unavailable module=pyyaml'
  exit 78
fi

if [ ! -r "$template" ] || [ ! -r "$jail" ]; then
  printf '%s\n' "tf_render_check=invalid-repo path=$template"
  exit 78
fi

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

# Config minima que solo renderiza la plantilla. Sin providers ni
# backend, asi que no hace falta ninguna credencial.
cat > "$tmp/main.tf" <<EOF
terraform {
  required_version = ">= 1.5"
}
output "cloud_init" {
  value = templatefile(
    "$root/$template",
    {
      admin_user       = "ubuntu"
      admin_password   = ""
      ssh_public_key   = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAICIFPLACEHOLDER"
      workspace_device = "/dev/sda"
      workspace_mount  = "/opt/seclab-sbf/workspace"
      seclab_sshd_jail = indent(6, join("", ["\\n", file("$root/$jail")]))
    }
  )
}
EOF

if ! terraform -chdir="$tmp" init -backend=false -input=false >/dev/null 2>&1; then
  printf '%s\n' 'tf_render_check=init-failed'
  exit 78
fi
if ! terraform -chdir="$tmp" apply -auto-approve -input=false >/dev/null 2>&1; then
  printf '%s\n' 'tf_render_check=render-failed'
  exit 78
fi
terraform -chdir="$tmp" output -raw cloud_init > "$tmp/cloud-init.yaml"

# El parseo y la comparacion los hace python, que ya esta verificado que
# existe. Compara byte a byte: la copia del host se valida con cmp en
# scripts/security/check-fail2ban.sh, y ahi importa que sea exacta.
if ! python3 - "$tmp/cloud-init.yaml" "$root/$jail" "$template" <<'PY'
import sys
import yaml

rendered, jail, template = sys.argv[1], sys.argv[2], sys.argv[3]
try:
    doc = yaml.safe_load(open(rendered))
except yaml.YAMLError as err:
    print("tf_render_check=invalid-yaml error=%s" % str(err).replace("\n", " ")[:200])
    sys.exit(1)

files = {f["path"]: f for f in doc.get("write_files", [])}
target = "/etc/fail2ban/jail.d/seclab-sshd.conf"
if target not in files:
    print("tf_render_check=missing-jail path=%s" % target)
    sys.exit(1)

expected = open(jail).read()
actual = files[target]["content"]
if actual != expected:
    # Se imprime la primera linea que difiere: si el bloque `content: |`
    # pierde la indentacion de la primera linea, el YAML sigue siendo
    # valido (una linea "# ..." en la columna 0 es un comentario) y lo
    # unico que se nota es que falta el arranque del archivo.
    want, got = expected.splitlines(), actual.splitlines()
    line = next(
        (n for n in range(max(len(want), len(got)))
         if (want[n:n + 1] or [None]) != (got[n:n + 1] or [None])),
        0,
    )
    print("tf_render_check=jail-drift path=%s linea=%d esperado=%r obtenido=%r" % (
        target, line + 1,
        (want[line] if line < len(want) else None),
        (got[line] if line < len(got) else None),
    ))
    sys.exit(1)
PY
then
  exit 78
fi

printf '%s\n' "tf_render_check=ok template=$template"
