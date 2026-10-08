#!/bin/sh
set -eu

image="${1:-${LAB_IMAGE:-seclab-sbf:full}}"
docker run --rm -i --read-only --network none --user tester \
  --tmpfs /tmp:rw,nosuid,nodev,mode=1777 --entrypoint /bin/zsh "$image" -f -s <<'CHECK'
set -eu
source /usr/local/share/seclab/pentest-lab/pentest-lab.plugin.zsh
fixture="$(mktemp -d /tmp/recon-shell.XXXXXX)"
trap 'rm -rf "$fixture"' EXIT
mkdir "$fixture/bin" "$fixture/work"
export RECON_SHELL_CALLS="$fixture/calls"
for tool in subfinder assetfinder findomain httpx; do
  cat > "$fixture/bin/$tool" <<'TOOL'
#!/bin/sh
printf '%s\n' "$0 $*" >> "$RECON_SHELL_CALLS"
printf '%s\n' 'candidate.example.test'
TOOL
  chmod +x "$fixture/bin/$tool"
done
export PATH="$fixture/bin:$PATH"
rehash
cd "$fixture/work"
_pt-recon-script() { return 1; }
for mode in dry-run run status filter; do
  case "$mode" in
    dry-run) arguments=(example.test --dry-run) ;;
    run) arguments=(example.test) ;;
    status) arguments=(status example.test) ;;
    filter) arguments=(filter candidates.txt scope.txt) ;;
  esac
  if pt-recon "${arguments[@]}" > "$fixture/stdout" 2> "$fixture/stderr"; then
    printf 'Error: pt-recon %s aceptó una ejecución sin pipeline.\n' "$mode" >&2
    exit 1
  fi
  if [[ -s "$RECON_SHELL_CALLS" || -n "$(ls -A)" ]]; then
    printf 'Error: pt-recon %s invocó herramientas o creó artefactos sin pipeline.\n' "$mode" >&2
    exit 1
  fi
  [[ -s "$fixture/stderr" ]]
done
pt-recon --help > /dev/null
cat > "$fixture/pipeline.py" <<'PIPELINE'
import json
import os
import sys
with open(os.environ['RECON_SHELL_CALLS'], 'a', encoding='utf-8') as stream:
    stream.write(json.dumps(sys.argv[1:]) + '\n')
raise SystemExit(7 if 'fail' in sys.argv else 0)
PIPELINE
_pt-recon-script() { printf '%s' "$fixture/pipeline.py"; }
pt-recon example.test --dry-run --json
pt-recon status example.test
pt-recon filter candidates.txt scope.txt
if pt-recon fail; then
  printf '%s\n' 'Error: pt-recon ocultó el fallo del pipeline.' >&2
  exit 1
else
  result=$?
  [[ "$result" -eq 7 ]]
fi
python3 - <<'ASSERT'
import json
import os
from pathlib import Path
actual = [json.loads(line) for line in Path(os.environ['RECON_SHELL_CALLS']).read_text().splitlines()]
expected = [
    ['run', 'example.test', '--dry-run', '--json'],
    ['status', 'example.test'],
    ['filter', 'candidates.txt', 'scope.txt'],
    ['run', 'fail'],
]
assert actual == expected, actual
ASSERT
CHECK
printf '%s\n' "recon_shell=ok imagen=$image missing_pipeline=blocked delegation=ok"
