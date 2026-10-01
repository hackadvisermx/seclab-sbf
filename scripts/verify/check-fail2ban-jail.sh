#!/bin/sh
set -eu

# Comprueba la jail de sshd con el propio fail2ban, en un contenedor
# desechable. Son las dos cosas que se pueden comprobar sin un host Linux:
#
#   1. Que fail2ban acepte el archivo del repo (`fail2ban-client -t`). Es
#      el validador real: caza backends que no existen, jails sin log, y
#      valores mal formados. Lo que NO caza es una clave mal escrita en
#      la jail: fail2ban acepta en silencio un `maxretryy` o un
#      `findtime` mal puesto, asi que ningun check de los de aqui lo
#      detectaria. Para eso hay que leer el archivo, que es lo que hace
#      `fail2ban-check` comparandolo con el desplegado en el host.
#   2. Que el filtro de sshd cuente las autenticaciones fallidas y no
#      cuente los logins correctos, y que cuente exactamente las que
#      hacen falta para alcanzar el umbral que declara la propia jail.
#      Si maxretry cambia, el log de ataque deja de cubrir el umbral y el
#      check falla, en vez de dar un OK que ya no significaria nada.
#
# Lo que NO comprueba: que la IP acaben bloqueada de verdad en nftables.
# Eso lo aplica fail2ban con sus propias acciones y necesita un host Linux
# real; se verifica en el nodo con `make fail2ban-check` y provocando
# fallos de autenticación a mano. Aqui no se levanta ninguna jail: solo
# se parsea la configuración y se pasa un log por el filtro.

# Imagen base, snapshot y versión de fail2ban: los mismos pines que usan
# los Dockerfiles del laboratorio (images/{base,full}/Dockerfile). El
# paquete sale del snapshot, así que resolverlo un día y otro da lo mismo.
base_image="docker.io/library/ubuntu@sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3"
snapshot="20261005T000000Z"
fail2ban_version="1.0.2-3ubuntu0.1"

jail="security/fail2ban/jail.d/seclab-sshd.conf"

if ! command -v docker >/dev/null 2>&1; then
  printf '%s\n' 'fail2ban_jail_check=unavailable command=docker'
  exit 78
fi

if [ ! -r "$jail" ]; then
  printf '%s\n' "fail2ban_jail_check=invalid-repo path=$jail"
  exit 78
fi

# El umbral de baneo lo declara la jail. El log de ataque tiene que
# producir justo ese numero de fallos, o el "atacante=N" de mas abajo no
# demuestra que se alcanzaria el ban.
maxretry="$(sed -n 's/^[[:space:]]*maxretry[[:space:]]*=[[:space:]]*\([0-9][0-9]*\).*/\1/p' "$jail" | head -1)"
case "$maxretry" in
  ''|*[!0-9]*) printf '%s\n' "fail2ban_jail_check=no-maxretry path=$jail"; exit 78 ;;
esac

root="$(pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

# Cinco fallos seguidos del mismo nodo: fuerza bruta contra root, tester
# y un usuario invalido, cada uno con el formato que emite sshd. Con
# maxretry=5 son justo los que disparan el baneo.
cat > "$tmp/ataque.log" <<'LOG'
Sep 29 22:10:01 ubuntu sshd[1234]: Failed password for invalid user root from 100.64.1.5 port 5555 ssh2
Sep 29 22:10:03 ubuntu sshd[1234]: Invalid user tester from 100.64.1.5 port 5556
Sep 29 22:10:05 ubuntu sshd[1234]: Failed password for tester from 100.64.1.5 port 5557 ssh2
Sep 29 22:10:07 ubuntu sshd[1234]: Failed publickey for ubuntu from 100.64.1.5 port 5558 ssh2: RSA SHA256:badkey
Sep 29 22:10:09 ubuntu sshd[1234]: Connection closed by authenticating user root 100.64.1.5 port 5559 [preauth]
LOG

# El trafico normal del operador: un login correcto y la linea de sesion.
# Ninguna de las dos puede sumar un fallo, o el operador se banea a si
# mismo por trabajar.
cat > "$tmp/legitimo.log" <<'LOG'
Sep 29 22:10:11 ubuntu sshd[2345]: Accepted publickey for ubuntu from 100.64.1.6 port 6001 ssh2
Sep 29 22:10:13 ubuntu sshd[2345]: pam_unix(sshd:session): session opened for user ubuntu by (uid=0)
LOG

docker run --rm \
  -v "$root/$jail:/etc/fail2ban/jail.d/seclab-sshd.conf:ro" \
  -v "$tmp:/logs:ro" \
  "$base_image" \
  sh -eu -c '
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq >/dev/null
    apt-get install -y -qq --no-install-recommends ca-certificates >/dev/null
    # ca-certificates sale del archivo vivo porque todavia no hay CA con
    # que verificar el snapshot. A partir de aqui, todo viene del snapshot.
    sed -i "s|http://ports.ubuntu.com/ubuntu-ports/|https://snapshot.ubuntu.com/ubuntu/'"$snapshot"'/|g" /etc/apt/sources.list.d/ubuntu.sources
    sed -i "/^Snapshot:/d" /etc/apt/sources.list.d/ubuntu.sources
    apt-get update -qq >/dev/null
    apt-get install -y -qq --no-install-recommends fail2ban='"$fail2ban_version"' >/dev/null
    dpkg-query -s fail2ban | sed -n "s/^Version: /fail2ban=/p"
    fail2ban-client -t
    for log in ataque legitimo; do
      printf "%s " "$log"
      fail2ban-regex "/logs/$log.log" /etc/fail2ban/filter.d/sshd.conf \
        | grep -E "^Lines: " | tail -1
    done
  ' > "$tmp/salida.txt" 2>&1 || true

# El codigo de salida del contenedor no distingue un fallo de instalacion
# de un rechazo de la configuracion, asi que se decide por lo que fallo
# imprimio y no por el estado.
if ! grep -q 'configuration test is successful' "$tmp/salida.txt"; then
  if grep -q 'ERROR: test configuration failed' "$tmp/salida.txt"; then
    printf '%s\n' 'fail2ban_jail_check=invalid-jail'
    sed 's/^/  /' "$tmp/salida.txt" | grep -E 'ERROR' | tail -5 >&2
  else
    printf '%s\n' 'fail2ban_jail_check=container-failed'
    sed 's/^/  /' "$tmp/salida.txt" | tail -10 >&2
  fi
  exit 78
fi

# `fail2ban-regex` imprime "Lines: N lines, I ignored, M matched, X missed".
# Se parsea M: los cinco fallos del atacante tienen que contar como cinco,
# y el login correcto y la linea de sesion tienen que contar como cero.
matched() {
  sed -n "s/^$1 Lines: [0-9]* lines, [0-9]* ignored, \([0-9]*\) matched.*/\1/p" "$tmp/salida.txt"
}

ataque_matched="$(matched ataque)"
legitimo_matched="$(matched legitimo)"

if [ "$ataque_matched" != "$maxretry" ]; then
  printf '%s\n' "fail2ban_jail_check=filter-missed-failures matched=$ataque_matched umbral=$maxretry"
  exit 78
fi
if [ "$legitimo_matched" != "0" ]; then
  printf '%s\n' "fail2ban_jail_check=filter-counted-legitimate matched=$legitimo_matched esperado=0"
  exit 78
fi

printf '%s\n' "fail2ban_jail_check=ok snapshot=$snapshot atacante=$ataque_matched umbral=$maxretry legitimo=$legitimo_matched"
printf '  %s\n' "$(grep -E '^fail2ban=' "$tmp/salida.txt")"
printf '%s\n' '  nota: el baneo efectivo en nftables no se comprueba aqui; requiere un host Linux'
