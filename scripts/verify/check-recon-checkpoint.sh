#!/bin/sh
set -eu
image="${1:-${LAB_IMAGE:-seclab-sbf:full}}"
tests="$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)/test_checkpoint_integrity.py"
docker run --rm --read-only --network none --user tester \
  --tmpfs /tmp:rw,nosuid,nodev,mode=1777 \
  --mount "type=bind,src=$tests,dst=/tmp/test_checkpoint_integrity.py,readonly" \
  -e CHECKPOINT_SCRIPTS=/usr/local/bin --entrypoint python3 "$image" /tmp/test_checkpoint_integrity.py
printf '%s\n' "installed_recon_checkpoint=ok imagen=$image modified=blocked corrupt=blocked unchanged=accepted network=none"
