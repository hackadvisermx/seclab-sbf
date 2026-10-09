# Fase 164: siguiente decisión ligada al último job

Fecha: 2026-10-09. Rama `phase/164-recon-next-decision`, base `c221db3`, worktree `/Users/castr/tmp/t01-next-decision`. Entrega parcial V3-02f.

## Problema comprobado y comportamiento

La reproducción aislada en `seclab-sbf:full-phase163`, sin red, creó un proyecto de fixture, un archivo de hosts anterior y un job terminado como `failed`. El endpoint de siguiente paso devolvía `recon` y comando `pt-recon`: la recomendación no consultaba el job persistido ni pedía revisar el fallo. La cobertura de archivos puede conservar información de ejecuciones anteriores y no acredita que el último job haya completado una etapa.

`GET /api/v1/checklist/{id}/next` ahora consulta el estado SQLite del proyecto/tipo antes de invocar pt-next. Para running/cancelling solicita esperar y revisar progreso; blocked dirige a Alcance/autorización y al motivo disponible en Reconocimiento; failed dirige a revisar motivo/log; cancelled/interrupted dirigen a revisar el historial antes de preparar un nuevo plan. Esas respuestas llevan `decision_job` con run_id, estado, etapa y modo, título/motivo, acción local (`scope` o `recon`), `command: null`, `ready_for_closure: false`, `prompt_available: false` y `prompt` vacío. No duplican errores, paths privados, comandos ni targets del job y no llaman al generador de prompts.

Sin job, o con completed/simulated, se conserva el contrato anterior de pt-next. Después de generar la recomendación se vuelve a consultar el job: si empezó o terminó con un estado que requiere revisión durante la generación, el resultado/prompt anterior se descarta. Fallo de lectura de estado devuelve 503 con un mensaje general, sin recomendar actividad a ciegas. Las lecturas son una fotografía del momento; no bloquean futuras transiciones ni conceden permiso de ejecución.

La UI muestra el job relacionado y navega solamente a Alcance o Reconocimiento. El botón de prompt queda deshabilitado visualmente; actualizar, entrar a Metodología, cambiar proyecto o recibir un cambio de job vuelve a consultar la decisión. Cada consulta retira comando/prompt anteriores; respuestas tardías, incluso de otro proyecto o después de desmontar, no se aplican. Al pedir prompt se revalida y actualiza también la tarjeta. Un error retira la recomendación anterior y permite reintentar. La cobertura conserva su cálculo existente y aclara que incluye documentación de ejecuciones anteriores.

## Validación

```sh
make verify
make build-full BUILD_TAG=-phase164
make dashboard-tests LAB_IMAGE=full-phase164 IMAGE_SOURCE=remote
npm --prefix dashboard/frontend test
npm --prefix dashboard/frontend run audit
npm --prefix dashboard/frontend run test:e2e
npm --prefix dashboard/frontend run test:e2e:integration
make smoke-test SCAN_IMAGE=seclab-sbf:full-phase164
make compose-config ENV_FILE=.env.example LAB_IMAGE=full-phase164
go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.12
make scan-image SCAN_IMAGE=seclab-sbf:full-phase164
```

- 183 Python, 195 backend y 118 frontend; audit 0. Siete pruebas nuevas de backend verifican prioridad ante archivos previos, seis estados, ausencia de prompts/datos privados, persistencia, aislamiento por proyecto/tipo, reconsulta durante generación, autenticación y estado indisponible. Cinco nuevas de frontend cubren enlace local, respuestas tardías, revalidación de prompt, errores/reintento y cambio de proyecto.
- 3 UI y 5 integraciones Chromium con tester temporal, contraseña aleatoria y contenedor `--network none`. El caso extendido conserva dos resultados distintos y un bloqueo real, recarga, verifica run_id y ausencia de comando/prompt y navega a Alcance. Captura `next-decision.png` inspeccionada; recursos/credenciales de fixture eliminados al finalizar.
- Imagen aislada `seclab-sbf:full-phase164`, hash de insumos `f10ff1fbd9e0b840`, idéntico al checkout. Build, smoke, Compose, Actionlint y gate CVE High/Critical aprobados bajo la política existente. CI del head exacto se registra al cerrar el PR. Sin dependencias ni excepciones nuevas.
- Logs, reproducción y captura en `tmp/phase164` del checkout principal; no forman parte de la imagen. Integración en [PR #184](https://github.com/hackadvisermx/seclab-sbf/pull/184) hacia `bootstrap/baseline`; cierre y CI del head exacto registrados en el PR.

## Compatibilidad, límites y reversión

No cambia tablas, permisos, pipeline ni contratos CLI. Reutiliza el último job conservado por fases152/158; no reconstruye jobs desde stdout ni archivos. La API de siguiente paso añade una decisión local para los seis estados descritos; el checklist, pt-next invocado directamente y jobs completed/simulated mantienen la heurística previa. La simulación no se convierte en prueba de actividad real.

La decisión de revisar persiste hasta que el último job cambia; abrir el panel no marca una revisión aceptada ni ejecuta un reintento. No crea una máquina de estados completa, eventos de aceptación humana, timeline, snapshots o procedencia finding/job. No intercepta terminal libre ni impide al operador usar otros controles del producto. Un job puede cambiar después de la lectura; la ejecución mantiene sus gates existentes de scope/plan. Revert restaura la recomendación anterior sin migración ni pérdida de jobs. Laboratorio vivo, imagen full y proyectos del owner intactos.

Merge sujeto a PR, revisión del diff, gates y CI aprobado del head exacto. La autorización temporal del owner vence el 2026-10-09 19:09:04 UTC; después se requiere aprobación individual según AGENTS.md.
