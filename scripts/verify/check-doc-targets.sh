#!/bin/sh
set -eu

# Comprueba que todo comando `make X` citado en la documentación exista
# como target en el Makefile.
#
# Existe porque se colaron seis comandos que no existen: en el README,
# `compose-vpn-tun-check`, `compose-vpn-status`, `compose-vpn-doctor`,
# `compose-proxy-status`, `compose-proxy-doctor` y `compose-proxy-stop`.
# Los seis estaban en el "Inicio rápido", o sea que quien los copiaba
# obtenía un error. Un documento con un comando inventado es peor que no
# escribirlo, así que esto se comprueba en vez de confiar en la lectura.
#
# Solo mira el nombre del target. No comprueba que los argumentos que le
# sigan sean los correctos, ni que el comando haga lo que dice el texto
# que lo acompaña. Es un guardia de typos, no un test de comportamiento.

targets="$(sed -n 's/^\([a-zA-Z0-9_.-]*\):.*/\1/p' Makefile)"

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

# Nombres de target documentados, con los wildcards que sí existen
# (tf-apply-* y compañía) filtrados.
grep -ohE 'make [a-z][a-z0-9-]{2,}' "$@" 2>/dev/null \
  | sed 's/^make //' | sort -u > "$tmp"

# Mencionados solo para decir que no se usen: AGENTS.md avisa de no
# inventar un target de pruebas. No es un comando que alguien vaya a
# copiar, asi que no debe contarse como referencia rota.
ignore='test'

missing=0
while read -r name; do
  [ -n "$name" ] || continue
  case "$name" in
    tf-apply-* | tf-plan-* | tf-destroy-* | env-copy-*) continue ;;
  esac
  case " $ignore " in
    *" $name "*) continue ;;
  esac
  if ! printf '%s\n' "$targets" | grep -qx -- "$name"; then
    printf '%s\n' "doc_check=missing-target target=$name" >&2
    missing=$((missing + 1))
  fi
done < "$tmp"

if [ "$missing" -ne 0 ]; then
  printf '%s\n' "doc_check=fail documentos=$* ausentes=$missing" >&2
  exit 78
fi

printf '%s\n' "doc_check=ok documentos=$*"
