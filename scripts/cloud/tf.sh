#!/bin/sh
# Envoltorio Terraform por stack: init/plan/apply/destroy/output.
# Uso: tf.sh <oci|azure|digitalocean> <init|plan|apply|destroy|output> [args...]
# Nunca recibe el .env de ejecución; el state va al backend remoto.
# Requiere deploy/backend-<stack>.hcl (ver *.example en cada stack).
set -eu

STACK="${1:-}"
OP="${2:-}"
shift 2 || true

case "$STACK" in
  oci | azure | digitalocean) ;;
  *)
    printf '%s\n' "uso: $0 <oci|azure|digitalocean> <init|plan|apply|destroy|output> [args...]" >&2
    exit 2
    ;;
esac

STACK_DIR="terraform/stacks/$STACK"
BACKEND_FILE="deploy/backend-$STACK.hcl"
if [ ! -f "$BACKEND_FILE" ]; then
  printf '%s\n' "falta $BACKEND_FILE; cópialo desde terraform/stacks/$STACK/backend.hcl.example y complétalo" >&2
  exit 2
fi

cd "$STACK_DIR"
case "$OP" in
  init) terraform init -backend-config="../../../$BACKEND_FILE" "$@" ;;
  plan | apply | destroy) terraform "$OP" "$@" ;;
  output) terraform output "$@" ;;
  *)
    printf '%s\n' "operación inválida: $OP (init|plan|apply|destroy|output)" >&2
    exit 2
    ;;
esac
