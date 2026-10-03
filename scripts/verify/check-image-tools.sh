#!/bin/sh
set -eu

# Comprueba que la imagen construida tenga las herramientas que el
# manifiesto declara, y que el manifiesto este sincronizado consigo mismo.
#
# Existe porque un Dockerfile puede construir bien y aun asi faltar un
# binario: un paquete que cambio de nombre entre versiones de Ubuntu, un
# artefacto que se dejo de copiar, o una entrada en el manifiesto que
# nunca llego a instalarse. Nada de eso lo detecta `docker build`, ni
# Hadolint, ni el escaneo de CVEs: el escaneo mira vulnerabilidades de lo
# que hay, no la ausencia de lo que deberia haber.
#
# Se ejecuta contra un contenedor desechable con `--entrypoint sh`, asi
# que no toca el laboratorio ni necesita `.env`: la lista de binarios es
# literal, no viene de la sesion de zsh del usuario.
#
# Uso: check-image-tools.sh [imagen]
# Por defecto comprueba $(LAB_IMAGE), que es la que produce el Makefile.

image="${1:-${LAB_IMAGE:-seclab-sbf:full}}"

# Subconjunto representativo, no la lista completa: son las herramientas
# que definen cada bloque (recon, web, explotacion, crack, reversing,
# terminal). Los 49 se validan contra el manifiesto mas abajo.
binaries="nmap httpx nuclei subfinder ffuf gobuster feroxbuster dalfox \
msfconsole nxc john hashcat wpscan bettercap s3scanner gdb-multiarch \
zsteg exiftool hexedit zsh ttyd sshd sqlmap pspy nikto enum4linux-ng"

nbins="$(printf '%s' "$binaries" | wc -w | tr -d ' ')"

missing=""
for t in $binaries; do
  if ! docker run --rm --entrypoint sh "$image" -c "command -v $t" >/dev/null 2>&1; then
    missing="$missing $t"
  fi
done

if [ -n "$missing" ]; then
  printf '%s\n' "image_tools=fail imagen=$image ausentes=$missing" >&2
  exit 78
fi

# El manifiesto tiene que cuadrar consigo mismo: cada herramienta de
# `installed` tiene entrada en `tools`, y al reves. Una entrada sin
# instalar es una promesa que la imagen no cumple.
count="$(docker run --rm --entrypoint python3 "$image" -c '
import json
d = json.load(open("/usr/local/share/seclab/tools.json"))
installed, tools = set(d["installed"]), set(d["tools"])
if installed != tools:
    raise SystemExit("fuera de sync: " + ", ".join(sorted(installed ^ tools)))
print(len(installed))
')" || {
  printf '%s\n' "image_tools=fail imagen=$image manifiesto=desincronizado" >&2
  exit 78
}

printf '%s\n' "image_tools=ok imagen=$image binarios=$nbins manifiesto=$count"
