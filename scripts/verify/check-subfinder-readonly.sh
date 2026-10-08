#!/bin/sh
set -eu

image="${1:-${LAB_IMAGE:-seclab-sbf:full}}"
output="$(docker run --rm --read-only --network none --user tester \
  --entrypoint /usr/bin/subfinder "$image" -version 2>&1)" || {
  printf '%s\n' "subfinder_readonly=fail imagen=$image" >&2
  exit 1
}
case "$output" in
  *'Could not create provider config file'*|*'ERR'*|*'FTL'*)
    printf '%s\n' "subfinder_readonly=fail imagen=$image error=configuracion-no-precargada" >&2
    exit 1
    ;;
esac
output="$(docker run --rm -i --read-only --network none --user tester \
  -e HOME=/root -e STATE_DIR=/tmp/dashboard-state \
  --tmpfs /tmp:rw,nosuid,nodev,mode=1777 --entrypoint /bin/bash "$image" -s 2>&1 <<'CHECK'
set -euo pipefail
source <(sed '/^exec /,$d' /usr/local/bin/dashboard-service)
test "$HOME" = /home/tester
subfinder -version
CHECK
)" || {
  printf '%s\n' "subfinder_readonly=fail imagen=$image error=entorno-dashboard" >&2
  exit 1
}
case "$output" in
  *'ERR'*|*'FTL'*)
    printf '%s\n' "subfinder_readonly=fail imagen=$image error=arranque-dashboard" >&2
    exit 1
    ;;
esac
printf '%s\n' "subfinder_readonly=ok imagen=$image dashboard_home=ok"
