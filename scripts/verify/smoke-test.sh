#!/bin/sh
set -eu

# Smoke test del contenedor del laboratorio.
# Ejecuta verificaciones dentro de un contenedor efimero sin requerir .env
# ni levantar servicios en segundo plano:
# 1. Permisos y existencia de /workspace para el usuario tester
# 2. Carga limpia de Zsh y funciones de pentest-lab (pt-help)
# 3. Disponibilidad y ejecucion basica de runtimes (python, ruby, perl)
# 4. Disponibilidad y respuesta de herramientas clave
# 5. Helper de proxy pt-forward / proxy-control
#
# Uso: smoke-test.sh [imagen]

image="${1:-${LAB_IMAGE:-seclab-sbf:full}}"

if ! command -v docker >/dev/null 2>&1; then
  printf '%s\n' "smoke_test=skipped docker=no-encontrado" >&2
  exit 78
fi

if ! docker image inspect "$image" >/dev/null 2>&1; then
  printf '%s\n' "smoke_test=fail imagen=$image error=imagen-no-encontrada" >&2
  exit 78
fi

printf '%s\n' "==> Ejecutando smoke test sobre $image..."

# Ejecutamos las validaciones en un solo contenedor efimero
docker run --rm --entrypoint /bin/sh "$image" -c '
set -eu

# 1. Workspace y usuario tester
id tester >/dev/null 2>&1 || { echo "tester user missing" >&2; exit 1; }
test -d /workspace || { echo "/workspace missing" >&2; exit 1; }
su - tester -c "touch /workspace/.smoke-test && rm -f /workspace/.smoke-test" || {
  echo "workspace not writable by tester" >&2
  exit 1
}

# 2. Runtimes
python3 -c "import urllib3, requests, impacket; print(\"python_ok\")" >/dev/null
ruby -e "puts \"ruby_ok\"" >/dev/null
perl -e "print \"perl_ok\"" >/dev/null

# 3. Zsh interactivo y pt-help
su - tester -s /bin/zsh -c "zsh -i -c \"pt-help >/dev/null\"" 2>/dev/null || {
  echo "zsh pt-help failed" >&2
  exit 1
}

# 4. Herramientas clave responden correctamente
nmap -V >/dev/null
msfconsole -v >/dev/null
nxc --help >/dev/null
sqlmap --version >/dev/null
pspy -h >/dev/null
enum4linux-ng -h >/dev/null
hashcat --version >/dev/null
chisel --version >/dev/null
ligolo-proxy -version >/dev/null 2>&1 || true
proxychains4 curl -h >/dev/null

# 5. pt-forward / proxy-control sintaxis y estado base
pt-forward status >/dev/null 2>&1 || test $? -eq 1
' || {
  printf '%s\n' "smoke_test=fail imagen=$image" >&2
  exit 1
}

/bin/sh "$(dirname "$0")/check-subfinder-readonly.sh" "$image"
/bin/sh "$(dirname "$0")/check-recon-shell.sh" "$image"
/bin/sh "$(dirname "$0")/check-finding-defaults.sh" "$image"
/bin/sh "$(dirname "$0")/check-finding-manifest.sh" "$image"
/bin/sh "$(dirname "$0")/check-installed-checklist.sh" "$image"
/bin/sh "$(dirname "$0")/check-recon-cli-decision.sh" "$image"
/bin/sh "$(dirname "$0")/check-recon-checkpoint.sh" "$image"

printf '%s\n' "smoke_test=ok imagen=$image"
