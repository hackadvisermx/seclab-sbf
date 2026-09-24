#!/bin/sh
set -eu

if [ "$(uname -s)" != "Linux" ]; then
  printf '%s\n' "tailscale_check=skipped platform=$(uname -s)"
  exit 0
fi

if ! command -v tailscale >/dev/null 2>&1; then
  printf '%s\n' 'tailscale_check=unavailable command=tailscale'
  exit 78
fi

if ! tailscale status --json >/dev/null 2>&1; then
  printf '%s\n' 'tailscale_check=status-failed'
  exit 78
fi

if tailscale serve status >/dev/null 2>&1; then
  printf '%s\n' 'tailscale_check=ok serve-status=available'
else
  printf '%s\n' 'tailscale_check=ok serve-status=unavailable'
fi
