# Fase 1 — Suministro, imagen base y CI

## Estado

La implementación local de la fase 1 está completa. La imagen base es un esqueleto reproducible. No hay publicación: la imagen se construye en la máquina que la usa y se revisa con `make scan-image`.

## Artefactos

- `images/base/Dockerfile`: imagen mínima Ubuntu 24.04 fijada por digest.
- `.dockerignore`: excluye secretos, workspace, VPN, state y archivos de diseño del contexto Docker.
- `supply-chain/tools.lock.yaml`: digests del snapshot de Ubuntu y hashes de artefactos por plataforma.
- `supply-chain/shell.lock.yaml`: commits exactos de Oh My Zsh y plugins seleccionados.
- `supply-chain/actions.lock.yaml`: tags, SHAs y versiones de Actions/scanners.
- `.github/workflows/security.yml`: secret scan, Trivy, Hadolint, ShellCheck, Actionlint y dependency review.
- `.github/dependabot.yml`: actualizaciones de Docker y GitHub Actions.
- `.github/CODEOWNERS`: ownership de workflows, imágenes y supply chain.
- `Makefile`: verificaciones locales de Gitleaks, Hadolint y ShellCheck.

## Imagen base

```text
docker.io/library/ubuntu@sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3
```

Sin registry no hay manifest ni digest publicado. `supply-chain/tools.lock.yaml` conserva los hashes de los artefactos por arquitectura, y cada imagen local registra en `seclab.build-inputs` el hash del código del que salió.

## Verificación local

```text
make verify
go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.12
BUILDKIT_PROGRESS=plain docker buildx build --progress=plain --file images/base/Dockerfile --tag seclab-sbf:base --load .
docker run --rm seclab-sbf:base /bin/bash -lc 'test -d /workspace; grep -q "Ubuntu 24.04" /etc/os-release'
docker image inspect seclab-sbf:base
```

`make verify` ejecuta:

- `gitleaks dir . --redact --no-banner`.
- `hadolint images/base/Dockerfile`.
- `shellcheck` sobre scripts versionados.

El daemon de Docker está activo. La imagen nativa `linux/arm64` se construyó y el smoke test confirmó `/workspace`, Ubuntu 24.04 y la arquitectura `aarch64`; la misma imagen se construyó nativa en `linux/amd64` para el host OCI.

## Límites de esta fase

- No existe todavía `compose.yaml` ni una imagen `light/full` ejecutable.
- No hay scripts runtime, shell plugins instalados ni proxy/VPN implementados.
- El workflow de release es una configuración verificable, no evidencia de que una publicación ya haya ocurrido.
- Las excepciones de CVEs y los artefactos de release deben revisarse antes de habilitar tags de producción.
