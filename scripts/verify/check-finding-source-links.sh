#!/bin/sh
set -eu
image="${1:-${LAB_IMAGE:-seclab-sbf:full}}"
test_file="$(cd "$(dirname "$0")" && pwd)/test_finding_source_links.py"
docker run --rm --read-only --network none --user tester \
  --tmpfs /tmp:rw,nosuid,nodev,mode=1777 \
  -v "$test_file:/tmp/test_finding_source_links.py:ro" \
  -e FINDING_SCRIPTS=/usr/local/bin --entrypoint python3 "$image" \
  /tmp/test_finding_source_links.py
printf '%s\n' 'finding_source_links=ok installed=1 readonly=1 network=none'
