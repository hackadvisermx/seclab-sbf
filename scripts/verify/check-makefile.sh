#!/bin/sh
set -eu

# Comprueba que el Makefile no tenga recetas partidas de forma accidental
# entre lineas fisicas.
#
# Existe por un fallo que solo aparecia en CI. Al anadir una entrada al
# texto de `make help`, se metio un salto de linea dentro de una cadena
# de comillas simples. Make no se entero: leyo la linea siguiente como
# una regla nueva, porque contenia dos puntos en `Variables:`. El
# resultado fue que `doc-targets-check` acquires como prerrequisito el
# fichero `ENV_FILE`, que no existe y no tiene regla que lo cree:
#
#   make: *** No rule to make target 'ENV_FILE', needed by
#   'doc-targets-check'.  Stop.
#
# Lo grave: en macOS pasa. El make de Apple es GNU Make 3.81 y tolera la
# regla espuria; el runner de CI es Ubuntu 24.04 con GNU Make 4.3 y
# falla. O sea que `make verify` en verde no demuestra nada sobre el
# Makefile. El texto de help es un bloque enorme de comillas simples en
# una sola linea, que es justo donde es facil partirlo sin darse cuenta.
#
# El invariante es simple: toda linea de receta (las que empiezan por
# tabulador) tiene un numero par de comillas simples. Una receta con un
# numero impar deja la cadena abierta y todo lo que viene despues se
# escapa de la comilla.

file="${1:-Makefile}"

if [ ! -f "$file" ]; then
  printf '%s\n' "makefile_check=fail falta=$file" >&2
  exit 78
fi

bad=0
awk -v f="$file" '
  /^\t/ {
    line = $0
    n = gsub(/'"'"'/, "", line)
    if (n % 2 == 1) {
      printf "%s:makefile_check=unbalanced-quote line=%d comillas=%d\n", f, NR, n
      bad = 1
    }
  }
  END { exit bad }
' "$file" || bad=1

if [ "$bad" -ne 0 ]; then
  printf '%s\n' "makefile_check=fail fichero=$file" >&2
  exit 78
fi

recipes="$(grep -c '^\t' "$file" 2>/dev/null || printf '%s' 0)"
printf '%s\n' "makefile_check=ok fichero=$file recetas=$recipes"
