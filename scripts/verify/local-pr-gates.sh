#!/bin/sh
# Gates locales de un PR: una imagen aislada y ningún push ni arranque del lab.
set -eu

root=$(cd -- "$(dirname -- "$0")/../.." && pwd)
cd "$root"
image=${LOCAL_GATE_IMAGE:-seclab-sbf:full-local-pr}
base_image=${LOCAL_GATE_BASE_IMAGE:-seclab-sbf:base}
mode=${1:-check}
case "$mode" in
  check|build) ;;
  *) printf 'Uso: LOCAL_GATE_IMAGE=... LOCAL_GATE_BASE_IMAGE=... %s [build|check]\n' "$0" >&2; exit 2 ;;
esac

expected=$(python3 scripts/build-inputs.py full)
if [ "$mode" = build ]; then
  docker image inspect "$base_image" >/dev/null 2>&1 || {
    printf 'Falta la imagen base local %s; prepara una base verificada primero.\n' "$base_image" >&2
    exit 1
  }
  base_expected=$(python3 scripts/build-inputs.py base)
  base_actual=$(docker image inspect -f '{{ index .Config.Labels "seclab.build-inputs" }}' "$base_image")
  if [ "$base_actual" != "$base_expected" ]; then
    printf 'Base local obsoleta: %s (esperado %s, actual %s).\n' "$base_image" "$base_expected" "$base_actual" >&2
    exit 1
  fi
  BUILDKIT_PROGRESS=plain docker buildx build --progress=plain \
    --build-arg "BASE_IMAGE=$base_image" --file images/full/Dockerfile \
    --label "seclab.build-inputs=$expected" --tag "$image" --load .
fi

docker image inspect "$image" >/dev/null 2>&1 || {
  printf 'Falta %s. Ejecuta este runner con build y una base local verificada.\n' "$image" >&2
  exit 1
}
actual=$(docker image inspect -f '{{ index .Config.Labels "seclab.build-inputs" }}' "$image")
if [ "$actual" != "$expected" ]; then
  printf 'Imagen obsoleta: %s (esperado %s, actual %s).\n' "$image" "$expected" "$actual" >&2
  exit 1
fi
printf 'local_gates_image=%s build_inputs=%s\n' "$image" "$actual"

make verify
if [ ! -x dashboard/frontend/node_modules/.bin/vite ]; then
  npm --prefix dashboard/frontend ci --prefer-offline --no-audit
fi
npm --prefix dashboard/frontend test
npm --prefix dashboard/frontend run build
npm --prefix dashboard/frontend run audit
docker run --rm --network none --entrypoint /opt/nxc/bin/python3 \
  -e PYTHONPATH=/usr/local/share/seclab/dashboard/backend \
  -e DASHBOARD_PASSWORD=dashboard-test-fixture-only \
  -e DASHBOARD_ALLOWED_HOSTS=localhost,127.0.0.1,testserver \
  -v "$root/dashboard/backend:/usr/local/share/seclab/dashboard/backend:ro" \
  -v "$root/dashboard/backend/tests:/tests:ro" "$image" \
  -m unittest discover -s /tests -v
npm --prefix dashboard/frontend run test:e2e
make smoke-test SCAN_IMAGE="$image"

# Los archivos se cachean localmente y se verifican contra el lock. El primer
# uso puede descargar releases de linters, sin consumir minutos de Actions.
mkdir -p tmp/local-ci-linters
docker run --rm -v "$root:/repo:ro" -v "$root/tmp/local-ci-linters:/cache" \
  --entrypoint python3 "$image" /repo/scripts/install-ci-linters.py \
  --cache /cache/archives --destination /cache/bin
docker run --rm --network none -v "$root:/repo:ro" \
  -v "$root/tmp/local-ci-linters:/cache:ro" -w /repo \
  --entrypoint /cache/bin/actionlint "$image"

# Trivy comparte cache; ejecutar secuencialmente evita locks entre scan y SBOM.
make scan-image SCAN_IMAGE="$image"
make sbom SCAN_IMAGE="$image"
printf 'local_pr_gates=ok image=%s build_inputs=%s\n' "$image" "$actual"
