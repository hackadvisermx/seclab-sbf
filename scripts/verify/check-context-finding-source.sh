#!/bin/sh
set -eu
image="${1:-${LAB_IMAGE:-seclab-sbf:full}}"
test_file="$(cd "$(dirname "$0")" && pwd)/test_context_finding_source.py"
docker run --rm --read-only --network none --user tester \
  --tmpfs /tmp:rw,nosuid,nodev,mode=1777 \
  -v "$test_file:/tmp/test_context_finding_source.py:ro" \
  -e CONTEXT_SCRIPTS=/usr/local/bin --entrypoint python3 "$image" \
  /tmp/test_context_finding_source.py
printf '%s\n' 'context_finding_source=ok installed=1 readonly=1 network=none'
