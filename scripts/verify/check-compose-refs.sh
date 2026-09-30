#!/bin/sh
set -eu

# Comprueba que cada `dockerfile:` de un compose apunte a un fichero que
# exista en el repo, y que la imagen por defecto no sea una que ya no se
# construye.
#
# Existe por un fallo real: al fusionar `light` en `full` se borro
# images/light/Dockerfile, pero compose.yaml y compose.local.yaml
# seguian diciendo `dockerfile: images/light/Dockerfile`, y
# compose.vpn-inside.yaml seguia por defecto en seclab-sbf:light. Todo
# el suite siguió en verde, porque `docker compose config` solo
# renderiza: no comprueba que la ruta exista. El fallo salia al primer
# `compose build` con un error de contexto sin relacion aparente con el
# cambio.
#
# El rango es deliberadamente estrecho: mira rutas de ficheros y tags de
# imagen, no valida el compose entero. Eso lo hace `compose-config`.

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

missing=0
seen=0

for f in "$@"; do
  [ -f "$f" ] || continue

  # Rutas de Dockerfile declaradas en un servicio build. Sin comillas
  # simples ni dobles, que es como estan escritas en el compose.
  sed -n 's/^[[:space:]]*dockerfile:[[:space:]]*//p' "$f" \
    | sed 's/"//g; s/'"'"'//g' > "$tmp"
  while read -r df; do
    [ -n "$df" ] || continue
    seen=$((seen + 1))
    if [ ! -f "$df" ]; then
      printf '%s\n' "compose_ref=missing-dockerfile compose=$f dockerfile=$df" >&2
      missing=$((missing + 1))
    fi
  done < "$tmp"

  # Tags de imagen por defecto ${VAR:-seclab-sbf:algo}: tienen que existir
  # como LAB_IMAGE en el Makefile, que es quien produce ese tag.
  sed -n 's/.*\${[A-Z_]*:-\(seclab-sbf:[a-z0-9-]*\)}.*/\1/p' "$f" \
    | sort -u > "$tmp"
  while read -r tag; do
    [ -n "$tag" ] || continue
    seen=$((seen + 1))
    escaped="$(printf '%s' "$tag" | sed 's/[:/]/\\&/g')"
    if ! grep -qE "^[[:space:]]*LAB_IMAGE[[:space:]]*\??=[[:space:]]*${escaped}[[:space:]]*$" Makefile; then
      printf '%s\n' "compose_ref=stale-image compose=$f image=$tag" >&2
      missing=$((missing + 1))
    fi
  done < "$tmp"
done

if [ "$missing" -ne 0 ]; then
  printf '%s\n' "compose_ref=fail compose=$* referencias=$seen rotas=$missing" >&2
  exit 78
fi

printf '%s\n' "compose_ref=ok compose=$* referencias=$seen"
