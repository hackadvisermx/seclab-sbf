#!/bin/sh
set -eu

test -d /workspace
test -r /etc/os-release
test -x /usr/local/bin/base-entrypoint
printf 'base-health=ok\n'
