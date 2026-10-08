# Fase 158: bloqueos de alcance al arrancar

Fecha: 2026-10-08. Rama `phase/158-recon-startup-block`, base `a24fa16`, worktree `/Users/castr/tmp/t01-startup-block`. V3-02d.

## Problema reproducido y cambio

Con target.yaml inválido, el pipeline termina antes de crear summary y el dashboard guardaba `failed / Código de salida: 1`. La regresión nativa falla así en `full-phase157`. Una revisión que cambia entre preflight del backend y entrada al CLI producía la misma clasificación genérica.

El runner abre un archivo temporal privado sin nombre persistente y entrega su descriptor al pipeline, junto a run_id. Ante ScopeError u OSError inicial atrapado en `cmd_run`, el pipeline escribe un resultado v1 ligado a run/etapa con clase y motivo. El worker lee máximo 16 KiB y valida versión, run, etapa, estado, clase y motivo. ScopeError con salida no cero se conserva como `blocked`; OSError sigue `failed` con razón técnica. Cancelación mantiene prioridad, salida cero no se vuelve bloqueo y un payload ausente/inválido/antiguo conserva fallback previo.

No se clasifican errores por palabras de stdout ni se escribe un summary artificial. Las herramientas hijas cierran descriptores mediante el comportamiento normal de subprocess; este descriptor solo se entrega explícitamente al pipeline. No constituye una frontera contra programas del mismo tester.

El canal es opcional: CLI normal conserva stdout/stderr y código 1 ante estos rechazos. Una variable de descriptor inválida no oculta el error ni cambia su salida. Summary y artefactos previos permanecen intactos en los casos comprobados de YAML inválido/plan cambiado antes de las etapas; el log del dashboard añade su lanzamiento/error como antes. Fallos posteriores siguen usando summary correlacionado.

La UI existente muestra bloqueo, motivo y revisión de scope, y el historial persiste ese resultado tras recarga. Los contadores del workspace anterior no acreditan finalización de este job.

## Validación

- 176 Python (`make verify`); canal opcional, CLI JSON/error y ausencia de escrituras en workspace ante scope inválido.
- 162 backend: pipeline instalado con YAML inválido y plan cambiado al entrar; artifacts anteriores; persistencia; payload fuera de límite/inválido/otro run/etapa; stdout adversarial; cancelación; regresiones del lease y shutdown.
- 103 frontend, audit 0; 2 UI y 4 integraciones Chromium aprobadas en contenedor sin red con tester temporal. Screenshot `startup-block.png` inspeccionado; recarga conserva motivo/historial y summary sintético previo.
- Imagen aislada `seclab-sbf:full-phase158`, hash `22039ba16fa36bf2`, insumos coincidentes. Build, smoke, Compose `.env.example`, Actionlint y gate CVE High/Critical aprobados bajo política vigente. Sin dependencias ni excepciones nuevas.
- Recursos de Playwright/credenciales eliminados; laboratorio vivo, proyectos del owner e imagen `seclab-sbf:full` intactos.

```sh
make verify
make build-full BUILD_TAG=-phase158
make dashboard-tests LAB_IMAGE=full-phase158 IMAGE_SOURCE=remote
npm --prefix dashboard/frontend test
npm --prefix dashboard/frontend run audit
npm --prefix dashboard/frontend run test:e2e
npm --prefix dashboard/frontend run test:e2e:integration
make smoke-test SCAN_IMAGE=seclab-sbf:full-phase158
make compose-config ENV_FILE=.env.example LAB_IMAGE=full-phase158
go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.12
make scan-image SCAN_IMAGE=seclab-sbf:full-phase158
```

## Límites y reversión

No modifica registros históricos ni completa timeline, evidencia o revisión humana de findings. No cambia autorización ni scope. Fallos ajenos al try de `cmd_run`, sintaxis CLI errónea o falta de canal válido siguen el fallback genérico; no se infiere un bloqueo. Un ScopeError posterior a preparación de directorios puede conservar esos efectos locales existentes; no se afirma que todos los rechazos sean previos a cualquier escritura o tráfico pasado.

La prueba de YAML inválido también hace visibles errores preexistentes de lectura del scope en otros endpoints; esta fase no cambia esos lectores. Solo Chromium y Docker Desktop macOS comprobados. Revert restaura clasificación anterior sin migración de datos. PR, CI y merge bajo autorización temporal del owner hasta 2026-10-09 19:09:04 UTC; después vuelve aprobación individual.
