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
policy="security/policies/nftables-lab.nft"
unit="security/systemd/seclab-nftables.service"
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

if [ ! -r "$template" ] || [ ! -r "$jail" ] || [ ! -r "$policy" ] || [ ! -r "$unit" ]; then
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
      workspace_mount  = "/opt/seclab-sbf/workspace"
      seclab_sshd_jail = indent(6, join("", ["\\n", file("$root/$jail")]))
      # El firewall del host y su unidad se renderizan igual que la jail, y
      # con el mismo fallo posible: indent() no toca la primera linea, asi que
      # sin el "\n" inicial la linea "define" de la politica se queda en la
      # columna 0 y el YAML se rompe al aplicar, no antes. Por eso tambien
      # entran en esta comprobacion, y no solo en terraform validate.
      seclab_nftables_policy = indent(6, join("", ["\\n", file("$root/$policy")]))
      seclab_nftables_unit   = indent(6, join("", ["\\n", file("$root/$unit")]))
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
if ! python3 - "$tmp/cloud-init.yaml" "$root/$jail" "$template" "$root/$policy" "$root/$unit" <<'PY'
import sys
import yaml

rendered, jail, template, policy, unit = sys.argv[1:6]
try:
    doc = yaml.safe_load(open(rendered))
except yaml.YAMLError as err:
    print("tf_render_check=invalid-yaml error=%s" % str(err).replace("\n", " ")[:200])
    sys.exit(1)

for idx, cmd in enumerate(doc.get("runcmd", [])):
    if not isinstance(cmd, (str, list)):
        print("tf_render_check=invalid-runcmd index=%d type=%s val=%r" % (idx, type(cmd).__name__, cmd))
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

# El firewall del host se compara con la MISMA logica que la jail, y por el
# mismo motivo: la politica que llega al host tiene que ser byte a byte la del
# repo. Si divergiera, se estaria auditando una cosa y aplicando otra, que es
# justo el fallo que el gate de CVEs evita en otro sitio.
for src, dst in ((policy, "/etc/nftables/seclab-lab.nft"),
                 (unit, "/etc/systemd/system/seclab-nftables.service")):
    if dst not in files:
        print("tf_render_check=missing-file path=%s" % dst)
        sys.exit(1)
    want_bytes = open(src).read()
    got_bytes = files[dst]["content"]
    if got_bytes != want_bytes:
        want, got = want_bytes.splitlines(), got_bytes.splitlines()
        line = next(
            (n for n in range(max(len(want), len(got)))
             if (want[n:n + 1] or [None]) != (got[n:n + 1] or [None])),
            0,
        )
        print("tf_render_check=file-drift path=%s linea=%d esperado=%r obtenido=%r" % (
            dst, line + 1,
            (want[line] if line < len(want) else None),
            (got[line] if line < len(got) else None),
        ))
        sys.exit(1)
PY
then
  exit 78
fi

printf '%s\n' "tf_render_check=ok template=$template"
