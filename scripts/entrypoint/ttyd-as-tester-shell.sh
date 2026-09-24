#!/bin/sh
set -eu

export TERM="${TERM:-xterm-256color}"
exec /usr/bin/tmux new-session -A -s pentest-lab /usr/bin/zsh -il
