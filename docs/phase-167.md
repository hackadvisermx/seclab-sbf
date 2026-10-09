# Fase 167: recompilación de Go para cerrar el gate de full

Fecha: 2026-10-09. Rama `phase/167-go-security-refresh`, base `83feed0`, worktree `/Users/castr/tmp/t01-go-security`. Corrección de supply chain previa a integrar fase166.

## Hallazgos y cambio

El escaneo actualizado de la imagen funcional de fase166 encontró 56 High en 28 binarios Go: herramientas, seis payloads de pivoting, fzf y pebble heredado de Ubuntu. Son dos identificadores repetidos por binario, CVE-2026-78667 (net/http) y CVE-2026-97031 (crypto/tls). Los avisos oficiales [GO-2026-6609](https://pkg.go.dev/vuln/GO-2026-6609) y [GO-2026-6607](https://pkg.go.dev/vuln/GO-2026-6607) identifican Go 1.26.9 y 1.27.2 como corregidos; [Go 1.26.9](https://go.dev/doc/devel/release) fue publicado el 2026-10-08.

GO_BUILDER y GO_UPSTREAM pasan a Go 1.26.9 con el índice oficial multiarch `sha256:f1f0bcc2c524a3ced375fcb4d1ecb7aa371aa7070e112599aaca45cc02d0101b`. Se conservan versiones/commits de herramientas, overrides, flags y GOTOOLCHAIN=local. El lockfile registra la toolchain actual y los hashes medidos de los assets que ya declaraba; no se sustituyen hashes por valores de releases upstream.

Full elimina `/usr/bin/pebble`, un ejecutable sin paquete dpkg heredado de Ubuntu. Ninguna fuente/entrypoint del laboratorio lo invoca; base-entrypoint y lab-entrypoint definen el arranque propio. No se retira ninguna herramienta del manifiesto. No cambia el Dockerfile de base, ni añade excepciones de Trivy, red o privilegios.

## Validación

```sh
make verify
make build-full BUILD_TAG=-phase167
make dashboard-tests LAB_IMAGE=full-phase167 IMAGE_SOURCE=remote
make smoke-test SCAN_IMAGE=seclab-sbf:full-phase167
make compose-config ENV_FILE=.env.example LAB_IMAGE=full-phase167
go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.12
make scan-image SCAN_IMAGE=seclab-sbf:full-phase167
make sbom SCAN_IMAGE=seclab-sbf:full-phase167
PLAYWRIGHT_LAB_IMAGE=seclab-sbf:full-phase167 npm --prefix dashboard/frontend run test:e2e:integration
```

Resultados finales: 184 Python, 195 backend, smoke/Compose/Actionlint y 5 integraciones Chromium contra la imagen phase167 aprobados. El gate High/Critical pasó con la política existente, sin nuevas excepciones. Imagen aislada `seclab-sbf:full-phase167`, hash de insumos `f45a5d6975be6214` igual al checkout; SBOM CycloneDX válido ligado a ese hash. Se midieron los 18 assets declarados (nueve herramientas por dos arquitecturas); los 24 binarios exportados arm64 coinciden byte a byte con los instalados. Gau, bettercap y s3scanner instalados también declaran Go 1.26.9: 27 binarios corregidos y pebble ausente. Evidencia/scan anterior, índice multiarch, builds y hashes en `tmp/phase166` y `tmp/phase167` del checkout principal. La exportación adicional de fzf, pspy y upstream-builder usa un stage scratch temporal fuera del repo para obtener assets linux/amd64 y linux/arm64; no compila Ruby por emulación ni construye/publica una imagen full amd64.

## Límites y operación

La imagen standalone de base conserva su digest upstream. Un scan exploratorio de esa base detectó vulnerabilidades OpenSSL preexistentes; esta fase no la declara apta para uso standalone. El runtime full instala sus paquetes de sistema mediante el mecanismo/snapshot existente y debe pasar su propio gate. El servicio `snapshot.ubuntu.com` respondió 502/503 durante intentos de reconstrucción: no se cambió a un repositorio móvil ni se omitieron CVEs. La corrección de base/snapshot se mantiene como trabajo separado.

Por petición explícita del owner, el repositorio `hackadvisermx/seclab-sbf` pasó a PUBLIC el 2026-10-09. Actions antes rechazaba los jobs por pagos/límite de gasto sin ejecutar pasos; el intento 2 de CI del PR186 comenzó a ejecutar tras el cambio. Esto no publica imágenes ni despliega el laboratorio.

Sin migración de proyectos ni cambios de comportamiento de las herramientas prometidos por la recompilación. Go 1.26.9 sí cambia bytes y metadatos de binarios, incluyendo fzf que antes usaba 1.25.13; se verifican comandos instalados. Revert restaura la toolchain anterior y reintroduce los CVEs conocidos. Laboratorio vivo y etiqueta full del owner intactos.

Integración por PR hacia bootstrap/baseline, diff revisado, gates y CI aprobado del head exacto bajo la autorización renovada hasta 2026-10-10 14:56:00 UTC. La fase166 debe integrar este merge y repetir sus gates antes de fusionarse.

PR [#187](https://github.com/hackadvisermx/seclab-sbf/pull/187) fusionado en `0e70e3d` el 2026-10-09 17:09:54 UTC; CI `37964014111`, intento 2, aprobado para head `1d98f83`. El cambio a público activó dependency-review; su primer intento detectó el grafo deshabilitado. Se habilitaron grafo/alertas de dependencias mediante la API oficial y el reintento pasó, sin omitir el chequeo.
