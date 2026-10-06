#!/bin/sh
set -eu

: "${TTYD_USER:?TTYD_USER is required}"
: "${TTYD_PASSWORD:?TTYD_PASSWORD is required}"

interface="${TTYD_INTERFACE:-0.0.0.0}"
port="${TTYD_PORT:-7681}"

export HOME=/home/tester
export USER="$TTYD_USER"
export LOGNAME="$TTYD_USER"
export SHELL=/usr/bin/zsh
export SECLAB_TMUX=1

exec /usr/bin/ttyd -d 3 -O -w /workspace -i "$interface" -p "$port" -c "$TTYD_USER:$TTYD_PASSWORD" -W /usr/local/bin/ttyd-as-tester-shell
