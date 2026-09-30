#!/bin/sh
set -eu

if [ ! -d /workspace ] || [ ! -w /workspace ]; then
  printf 'workspace is not writable: /workspace\n' >&2
  exit 1
fi

if [ "$#" -eq 0 ]; then
  set -- /bin/bash
fi

exec "$@"
