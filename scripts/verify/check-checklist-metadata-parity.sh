#!/bin/sh
set -eu
image="${1:-${LAB_IMAGE:-seclab-sbf:full}}"
test_file="$(cd "$(dirname "$0")" && pwd)/test_checklist_metadata_parity.py"
docker run --rm --read-only --network none --user tester \
  --tmpfs /tmp:rw,nosuid,nodev,mode=1777 \
  -v "$test_file:/tmp/test_checklist_metadata_parity.py:ro" \
  -e CHECKLIST_SCRIPTS=/usr/local/bin --entrypoint python3 "$image" \
  /tmp/test_checklist_metadata_parity.py
printf '%s\n' 'checklist_metadata_parity=ok installed=1 readonly=1 network=none'
