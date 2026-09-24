#!/bin/sh
set -eu

profile="${PENTEST_PROFILE:-light}"
case "$profile" in
  light|full) ;;
  *)
    printf 'invalid PENTEST_PROFILE: %s\n' "$profile" >&2
    exit 64
    ;;
esac

if [ ! -d /workspace ] || [ ! -w /workspace ]; then
  printf 'workspace is not writable: /workspace\n' >&2
  exit 1
fi

if [ "$#" -eq 0 ]; then
  set -- /bin/bash
fi

exec "$@"
