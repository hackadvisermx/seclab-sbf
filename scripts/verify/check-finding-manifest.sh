#!/bin/sh
set -eu
image="${1:-${LAB_IMAGE:-seclab-sbf:full}}"
test_file="$(cd "$(dirname "$0")" && pwd)/test_report_safety.py"
docker run --rm --read-only --network none --user tester \
  --tmpfs /tmp:rw,nosuid,nodev,mode=1777 \
  -v "$test_file:/tmp/test_report_safety.py:ro" \
  -e REPORT_SAFETY_SCRIPTS=/usr/local/bin --entrypoint python3 "$image" \
  /tmp/test_report_safety.py \
  ReportSafetyTests.test_finding_manifest_links_identity_source_and_selected_versions_in_both_formats \
  ReportSafetyTests.test_finding_manifest_marks_legacy_identity_missing_and_handles_empty_report \
  ReportSafetyTests.test_changed_finding_after_compile_blocks_export_without_replacing_prior_bundle \
  ReportSafetyTests.test_changed_report_after_compile_blocks_export_without_replacing_prior_bundle
printf '%s\n' 'finding_manifest=ok installed=1 readonly=1 network=none'
