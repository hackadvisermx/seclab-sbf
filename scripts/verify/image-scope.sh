#!/bin/sh
set -eu

# Dice si este PR toca algo que cambie la imagen, comparando los ficheros
# modificados con lo que los Dockerfiles copian de verdad.
#
# Existe por coste. El build completo tarda mas de 90 min en un runner de
# GitHub de 2 nucleos y el repo es privado, o sea que cada minuto se
# factura. Si el job de build corriera en todos los PRs, un cambio de
# README pagaria un build de dos horas.
#
# La lista de rutas vigiladas NO esta escrita a mano: se extrae de los
# COPY de images/*/Dockerfile. Si mañana el Dockerfile copia otro
# fichero, este filtro lo cubre sin que nadie recuerde editarlo. Un filtro
# escrito a mano se queda viejo y deja de detectar justo lo que queria
# detectar.
#
# Lo que no entra en la imagen no dispara el build: `scripts/verify/` se
# usa en el host, nunca se copia, asi que tocarlo no obliga a reconstruir
# 4,5 GB. Eso incluye a este propio script.
#
# Uso: image-scope.sh <base-sha> [<head-sha>]
# Salida: 0 si hay que reconstruir, 1 si no.
# En cualquier salida imprime los ficheros vigilados y los modificados.

base="${1:-}"
head="${2:-HEAD}"

if [ -z "$base" ]; then
  printf '%s\n' "image_scope=error falta=<base-sha>" >&2
  exit 78
fi

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

# Rutas de origen de cada COPY, sin los /out/ que salen de etapas previas.
grep -ohE '^COPY (--from=[a-zA-Z0-9-]+ +)?[^ ]+' images/*/Dockerfile 2>/dev/null \
  | sed -E 's/^COPY (--from=[a-zA-Z0-9-]+ +)?//' \
  | sed 's:/$::' \
  | grep -v '^/out/' \
  | grep -v '^$' \
  | sort -u > "$work/watched"

# El Makefile tambien cuenta: define los build-arg, la etiqueta de
# insumos y el propio BUILDX_CACHE, asi que cambiarlo cambia el build.
# Los Dockerfiles tambien, por si acaso el COPY no captura el cambio.
printf '%s\n' Makefile images | cat "$work/watched" - | sort -u > "$work/all"
mv "$work/all" "$work/watched"

git diff --name-only "$base" "$head" > "$work/changed" 2>/dev/null || : > "$work/changed"

printf '%s\n' "image_scope=watched rutas=$(wc -l < "$work/watched" | tr -d ' ')" \
  "image_scope=changed ficheros=$(wc -l < "$work/changed" | tr -d ' ')"

rebuild=no
while read -r f; do
  [ -n "$f" ] || continue
  while read -r w; do
    [ -n "$w" ] || continue
    case "$f" in
      "$w" | "$w"/*)
        printf '%s\n' "image_scope=hit fichero=$f regla=$w"
        rebuild=yes
        ;;
    esac
  done < "$work/watched"
done < "$work/changed"

if [ "$rebuild" = "yes" ]; then
  printf '%s\n' "image_scope=rebuild"
  exit 0
fi

printf '%s\n' "image_scope=skip"
exit 1