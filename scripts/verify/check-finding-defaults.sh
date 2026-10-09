#!/bin/sh
set -eu
image="${1:-${LAB_IMAGE:-seclab-sbf:full}}"
docker run --rm -i --read-only --network none --user tester \
  --tmpfs /tmp:rw,nosuid,nodev,mode=1777 --entrypoint /bin/zsh "$image" -f -s <<'CHECK'
set -eu
source /usr/local/share/seclab/pentest-lab/pentest-lab.plugin.zsh
fixture="$(mktemp -d /tmp/finding-defaults.XXXXXX)"
trap 'rm -rf "$fixture"' EXIT
export SECLAB_WORKSPACE_DIR="$fixture"
mkdir -p "$fixture/templates" "$fixture/engagements/fixture/evidence"
cp -R /usr/local/share/seclab/templates/. "$fixture/templates/"
chmod -R u+w "$fixture/templates"
printf 'engagement:\n  name: fixture\nscope:\n  in_scope:\n    domains: [example.test]\n' > "$fixture/engagements/fixture/target.yaml"
cd "$fixture/engagements/fixture"
# An inherited/global status must not become a decision for this finding.
status_arg=PROVEN
pt-finding new generic --title 'Fixture / sin confirmar' --asset example.test
for template_name in idor xss-reflected missing-rate-limit; do
  pt-finding new "$template_name" --template "$template_name" --asset example.test
done
for confirmed_status in proven verified confirmado ' PROVEN '; do
  if pt-finding new explicit --status "$confirmed_status" --asset example.test; then
    printf 'confirmación sin evidencia fue aceptada\n' >&2
    exit 1
  fi
  test ! -f evidence/explicit.md
done
pt-finding new explicit --status disproved --asset example.test
pt-finding new after-explicit --asset example.test
# A workspace seeded before phase 151 can still contain PROVEN placeholders.
sed -i 's/status: "CANDIDATE"/status: "PROVEN"/' "$fixture/templates/evidence.md"
pt-finding new old-template --asset example.test
# Exercise the fallback body when neither workspace nor repo template exists.
_pt-finding-list-templates() { return 1; }
_SECLAB_PLUGIN_DIR="$fixture/absent/plugin"
rm "$fixture/templates/evidence.md"
pt-finding new fallback --asset example.test
python3 - "$PWD" <<'ASSERT'
import pathlib, sys, yaml
root = pathlib.Path(sys.argv[1]) / 'evidence'
for path in root.glob('*.md'):
    metadata = yaml.safe_load(path.read_text().split('---\n', 2)[1])
    expected = 'DISPROVED' if path.stem == 'explicit' else 'CANDIDATE'
    assert metadata['status'] == expected, (path.name, metadata['status'], expected)
    assert metadata['asset'] == 'example.test', (path.name, metadata['asset'])
assert len(list(root.glob('*.md'))) == 8
assert 'Fixture / sin confirmar' in (root / 'generic.md').read_text()
ASSERT
CHECK
printf '%s\n' "finding_defaults=ok imagen=$image candidate=default explicit_status=preserved confirmation=guarded"
