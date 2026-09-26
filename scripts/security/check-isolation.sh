#!/bin/sh
set -eu

policy="security/policies/nftables-lab.nft"

if [ "$(uname -s)" != "Linux" ]; then
  printf '%s\n' "nftables_check=skipped platform=$(uname -s)"
  exit 0
fi

if ! command -v nft >/dev/null 2>&1; then
  printf '%s\n' 'nftables_check=unavailable command=nft'
  exit 78
fi

if [ "$(id -u)" -ne 0 ]; then
  printf '%s\n' 'nftables_check=requires-root'
  exit 77
fi

network_name="${SECLAB_DOCKER_NETWORK:-seclab-sbf_seclab}"
if command -v docker >/dev/null 2>&1; then
  network="$(docker network inspect -f '{{range .IPAM.Config}}{{.Subnet}} {{.Gateway}}{{end}}' "$network_name" 2>/dev/null || true)"
  case "$network" in
    '172.20.0.0/16 172.20.0.1') ;;
    '') printf '%s\n' "docker_network=not-found name=$network_name" ;;
    *) printf '%s\n' "docker_network=unexpected name=$network_name value=$network"; exit 78 ;;
  esac
fi

nft -c -f "$policy"
if ! grep -Fq 'hook prerouting' "$policy"; then
  printf '%s\n' 'nftables_check=invalid-hook expected=prerouting'
  exit 78
fi
printf '%s\n' 'nftables_check=ok policy=security/policies/nftables-lab.nft'
