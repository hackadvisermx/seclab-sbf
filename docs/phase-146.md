# Fase 146: revisión técnica v3 y fallo cerrado de pt-recon

Fecha: 2026-10-07. Base: `b353a46`. Rama: `phase/146-v3-flow-baseline`. Worktree: `/Users/castr/tmp/t01-v3-baseline`. PR en preparación hacia `bootstrap/baseline`; requiere aprobación explícita antes del merge.

## Cambio y resultado

La revisión V3-00 encontró que `pt-recon` podía saltar el pipeline seguro si faltaba el script: el fallback legacy ignoraba `--dry-run`, invocaba enumeradores y luego `httpx` sin matcher ni límites del engagement. Una simulación solicitada podía acabar en reconocimiento real. La regresión reprodujo esa rama en la imagen anterior con binarios de fixture, `--network none`, usuario tester y rootfs de solo lectura: el comando devolvía éxito.

Se elimina ese fallback. Si el pipeline no se puede localizar, el helper retorna 1 con una acción de recuperación antes de crear directorios o invocar herramientas. La ayuda permanece disponible; con script válido se conservan el despacho de `run/status/filter`, los argumentos y el código de salida del pipeline.

La entrega incorpora el backlog v3, [inventario de caminos y brechas comprobadas](v3-flujo-verificado.md) y [línea base técnica](baselines/v3-phase146.json). El recorder utiliza exclusivamente proyectos temporales y bloquea sockets/DNS. Los proveedores/sondeo de la tarea de reanudación son fixtures declarados; no se confunden con pruebas sobre un objetivo.

## Alcance de los archivos

- `shell/pentest-lab/pentest-lab.plugin.zsh`: bloqueo cuando falta pipeline; eliminación de ejecución legacy.
- `scripts/verify/check-recon-shell.sh`: Zsh real en imagen, sin red y como tester; prueba dry-run, run, status y filter sin pipeline, ayuda disponible y delegación exacta/código de fallo con pipeline de fixture.
- `scripts/verify/smoke-test.sh`: integra esa regresión al smoke test existente.
- `scripts/verify/record-v3-baseline.py`: registra simulación, filtrado, reanudación, reporte, paquete y cierre con fixtures sin aceptar targets externos.
- Documentación: backlog v3, referencias desde planes anteriores, revisión técnica, JSON de línea base, fase 146 y reconciliación del merge de fase 145.

## Validación local

| Comando | Resultado |
|---|---|
| `/bin/sh scripts/verify/check-recon-shell.sh seclab-sbf:full-phase145` | Reproduce fallo: `pt-recon dry-run aceptó una ejecución sin pipeline`, exit 1 del verificador |
| `make verify` | OK: 143 Python y gates de secretos, shell, Dockerfile, pines y Compose |
| `make build-full BUILD_TAG=-phase146` | OK: imagen aislada, `seclab.build-inputs=d99773a61672e933`, coincide con el checkout |
| `make smoke-test SCAN_IMAGE=seclab-sbf:full-phase146` | OK: herramientas/runtimes, configuración read-only Subfinder y nueva regresión Zsh |
| Recorder en host y contenedor `--read-only --network none --user tester` | OK: JSON idénticos, archivos sólo en `/tmp` del contenedor o temporales del host |
| `make compose-config ENV_FILE=.env.example` | OK |
| `go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.12` | OK |
| `make scan-image SCAN_IMAGE=seclab-sbf:full-phase146` | En curso; gate de High/Critical bajo la política existente |

No hay cambios de backend/frontend ni UI; las pruebas aplicables son Python, Zsh y smoke de imagen. La comprobación de límites DNS/redirects del pipeline conserva las pruebas existentes de `test_recon_safety.py`.

## Brechas siguientes y límites

V3-00 sigue en curso porque faltan sesiones con personas y métricas de uso real. La revisión técnica confirmó que `pt-report check` rechaza un activo explícitamente excluido, pero `pt-report build` evita ese gate y genera el reporte; `UNKNOWN` y la relación con evidencia original también necesitan reglas adicionales. V3-03a se adelanta como corrección P0 separada. El JSON de fixtures registra estos fallos; no los establece como expectativas que deban perpetuarse.

No se crea una garantía global sobre comandos de terminal. El inventario distingue matcher de engagement, sondeo controlado, políticas de rutas y shell libre. Sin cambios de dependencias ni migraciones. El alcance de proyectos existentes, el dominio UAZ, la etiqueta `seclab-sbf:full` y el contenedor en uso del owner no se modifican.

Reversión: revertir el PR y reconstruir una imagen aislada. Para usar el fix en un contenedor en vivo, después del merge el owner debe reconstruir y relanzar en el momento elegido; esta entrega no altera su sesión.
