#!/bin/sh
set -eu

# Avisa, antes de un apply, cuando el plan va a DESTRUIR algo.
#
# Existe por un motivo concreto: el stack de OCI tiene la instancia con
# metadata, y el provider trata ese map(string) como inmutable. Cualquier
# cambio en el cloud-init hace que la instancia entre en plan como "must
# be replaced", o sea destruir y recrear. El volumen del workspace
# sobrevive porque es un recurso aparte, pero se pierde la sesion de
# Tailscale y hay que volver a unir el nodo.
#
# Esto no decide nada: imprime el plan y sale con codigo distinto si ve
# una destruccion. Que el apply lo lance una persona es decision suya.
#
# NO lo ejecutes nunca con -out/-auto-approve enganchado: solo lee.

stack="${1:-oci}"
timeout_minutes="${PLAN_TIMEOUT_MINUTES:-20}"

if [ "$(uname -s)" != "Linux" ] && [ "$(uname -s)" != "Darwin" ]; then
  printf '%s\n' "tf_destroy_check=skipped platform=$(uname -s)"
  exit 0
fi

if ! command -v terraform >/dev/null 2>&1; then
  printf '%s\n' 'tf_destroy_check=unavailable command=terraform'
  exit 78
fi

case "$stack" in
  oci | azure | digitalocean) ;;
  *)
    printf '%s\n' "tf_destroy_check=invalid-stack stack=$stack" >&2
    exit 2
    ;;
esac

tmp_dir="$(mktemp -d)"
plan_file="$tmp_dir/plan.tfplan"
trap 'rm -rf "$tmp_dir"' EXIT

# El backend lo aporta tf.sh; este script no lo construye para no tener
# dos caminos al state. Si el stack no esta inicializado, se dice claro.
# Los tres stacks declaran su backend en el HCL, asi que -backend=false
# SIEMPRE falla: terraform se queja de que la configuracion cambio y pide
# -reconfigure. Por eso, si existe el fichero de backend se usa, y si no
# se dice que falta en vez de inventar un modo degradado que no lee el
# state real.
if [ ! -f "deploy/backend-$stack.hcl" ]; then
  printf '%s\n' "tf_destroy_check=sin-backend stack=$stack" >&2
  printf '%s\n' "tf_destroy_check=falta deploy/backend-$stack.hcl; copialo del .example del stack" >&2
  exit 78
fi

# shellcheck disable=SC2086 # el valor lleva espacios y el splitting es intencional
if ! terraform -chdir="terraform/stacks/$stack" init \
  -backend-config=../../../deploy/backend-$stack.hcl \
  -reconfigure -input=false >"$tmp_dir/init.log" 2>&1; then
  printf '%s\n' "tf_destroy_check=init-failed stack=$stack" >&2
  tail -10 "$tmp_dir/init.log" >&2
  exit 78
fi

# timeout_cmd se compone con un prefijo opcional, tambien con splitting
# deliberado. En macOS el binario es gtimeout.
timeout_cmd=""
if command -v gtimeout >/dev/null 2>&1; then
  timeout_cmd="gtimeout $((timeout_minutes * 60))"
elif command -v timeout >/dev/null 2>&1; then
  timeout_cmd="timeout $((timeout_minutes * 60))"
fi

# shellcheck disable=SC2086 # timeout_cmd es intencionadamente una linea
if ! $timeout_cmd terraform -chdir="terraform/stacks/$stack" plan -input=false -no-color -out="$plan_file" >"$tmp_dir/plan.log" 2>&1; then
  printf '%s\n' "tf_destroy_check=plan-failed stack=$stack" >&2
  tail -15 "$tmp_dir/plan.log" >&2
  exit 78
fi
rm -f "$plan_file.log"

summary="$(terraform -chdir="terraform/stacks/$stack" show -no-color "$plan_file" 2>/dev/null \
  | grep -E '^Plan: ' | tail -1)"

# "Plan: 2 to add, 0 to change, 2 to destroy." o "No changes."
to_destroy="$(printf '%s\n' "$summary" | sed -n 's/.*[^0-9]\([0-9]*\) to destroy.*/\1/p')"

if [ -z "$summary" ]; then
  printf '%s\n' "tf_destroy_check=unreadable stack=$stack"
  exit 78
fi

printf '%s\n' "tf_destroy_check=ok stack=$stack $summary"

# Un plan sin destrucciones no significa que todo este bien. Si la
# instancia no esta en el state, el plan va a decir "2 to add, 0 to
# destroy" y este check salia con 0, diciendo "me he quedado
# sin nodo" con "no vas a romper nada". El 2026-09-29 se perdio asi el
# nodo de OCI: el apply anterior lo habia destruido y este check no dijo
# nada. Un guard que da falsa tranquilidad es peor que no tenerlo, asi
# que se comprueba explicitamente que el recurso principal existe.
case "$stack" in
  oci) recurso="oci_core_instance.lab" ;;
  azure) recurso="azurerm_linux_virtual_machine.lab" ;;
  digitalocean) recurso="digitalocean_droplet.lab" ;;
  *) recurso="" ;;
esac

if [ -n "$recurso" ] && ! terraform -chdir="terraform/stacks/$stack" state list 2>/dev/null | grep -qx "$recurso"; then
  printf '%s\n' "tf_destroy_check=SIN-NODO stack=$stack falta=$recurso" >&2
  printf '%s\n' "tf_destroy_check=el plan va a CREAR el nodo de cero, no a actualizar uno" >&2
  printf '%s\n' "tf_destroy_check=tras el apply habra que rehacer el join de Tailscale" >&2
  printf '%s\n' "tf_destroy_check=si no querias perderlo, el apply anterior ya lo destruyo" >&2
  exit 1
fi

case "$summary" in
  *" 0 to destroy"*)
    exit 0
    ;;
esac

if [ "${to_destroy:-0}" -gt 0 ]; then
  printf '%s\n' "tf_destroy_check=DESTRUYE stack=$stack recursos=$to_destroy" >&2
  printf '%s\n' "tf_destroy_check=lee-el-plan stack=$stack antes de aplicar" >&2
  printf '%s\n' "tf_destroy_check=instancia-o-nodo = se recrea y se pierde la sesion de Tailscale" >&2
  printf '%s\n' "tf_destroy_check=workspace = volumen aparte, sobrevive; usa el snapshot o docs/backups.md" >&2
  exit 1
fi

exit 0
