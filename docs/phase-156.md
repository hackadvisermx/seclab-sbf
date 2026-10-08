# Fase 156: vista previa del reconocimiento

Fecha: 2026-10-08. Base `badcb49`, merge aprobado de #175. Rama `phase/156-recon-execution-preview`, worktree `/Users/castr/tmp/t01-recon-preview`. Entrega parcial V3-01c.

## Flujo visible

En la pestaña Reconocimiento, seleccionar etapa/modo y pulsar **Revisar plan sin tráfico**. La vista enumera clase pasiva/activa/local, targets conocidos, motivos del matcher, descartes, permisos/precondiciones que bloquean y límites activos, incluido timeout. Muestra hasta 50 targets/descartes por etapa, con contadores completos y aviso de truncamiento. Los límites de sondeo no se atribuyen a todas las herramientas pasivas.

Iniciar queda deshabilitado hasta una revisión válida. Un plan bloqueado ofrece revisar alcance/autorización o cambiar a simulación. Cambiar proyecto, etapa, modo o iniciar una carga de alcance invalida la revisión; respuestas tardías de una revisión descartada no habilitan el botón. La finalización tardía de la carga inicial de alcance conserva una vista previa más reciente.

En la cadena completa, sondeo y clasificación indican que los targets finales dependen de etapas anteriores. Descubrimiento nunca amplía autorización. Las consultas pasivas a bases derivadas de wildcard no se presentan como permiso activo sobre el apex.

## Contrato técnico

- CLI instalada: `pt-recon-pipeline preview <directorio> --stage probe [--dry-run]`, JSON. No ejecuta etapas ni herramientas, no resuelve DNS, no escribe artefactos/checkpoints/summary/logs y no crea jobs. Reutiliza carga/matcher/contrato/límites del pipeline.
- API autenticada: `POST /api/v1/recon/{id}/preview`, con `stage`, `dry_run` y tipo de proyecto. Timeout de 10 segundos; configuración ausente/inválida, timeout o respuesta inválida dan error y no habilitan lanzamiento.
- `scope_revision` conserva el hash del contrato. `plan_revision` añade directorio canónico del engagement, etapa, modo y líneas de listas locales de hosts/URLs. Hora y truncamiento de presentación no participan en el hash.
- El dashboard envía `expected_plan` al endpoint de ejecución. El backend recalcula la revisión y comprueba permisos/precondiciones antes de crear el job; un plan cambiado/bloqueado retorna 400 sin job. El worker entrega la revisión a `run --expected-plan`, que vuelve a comprobarla al entrar al pipeline. La revalidación existente antes de herramientas/nuevas conexiones sigue activa.
- API/CLI sin revisión esperada conservan compatibilidad y sus controles de autorización/alcance. La vista previa no otorga permisos ni congela archivos, DNS o resultados futuros durante el job. No equivale a una lista final inmutable para toda la cadena.

## Bug local reproducido

El helper `_tool` exigía permiso pasivo incluso para `gf`, que clasifica archivos locales. Una regresión sin permiso pasivo produjo fallo con el motivo de autorización; la llamada de clasificación ahora declara interacción local. Enumeradores y herramientas de URLs conservan permiso pasivo. Confirmado también con `gf` real en `full-phase156`, rootfs read-only, tester, sin capabilities y `--network none`: clasificación completa con ambos permisos falsos.

## Validación

- 175 Python (`make verify`), 150 backend, 102 frontend; npm audit 0 vulnerabilidades.
- Chromium: 2 pruebas UI y 3 de integración real aprobadas. Suites ejecutadas secuencialmente; recorrido completo repetido con datos sintéticos sin red.
- Imagen `seclab-sbf:full-phase156`, hash `02f714067585abe1`, coincide con insumos después de pruebas. Build, smoke, Compose `.env.example`, Actionlint y gate High/Critical aprobados bajo política vigente, sin nuevas excepciones.
- Confirmación adicional de `gf` real en contenedor sin red; no quedan contenedores de prueba ni credenciales.
- PR preparado hacia baseline; CI remoto y aprobación individual se consultan en el PR.

Comandos:

```sh
make verify
make build-full BUILD_TAG=-phase156
make dashboard-tests LAB_IMAGE=full-phase156 IMAGE_SOURCE=remote
npm --prefix dashboard/frontend test
npm --prefix dashboard/frontend run audit
npm --prefix dashboard/frontend run test:e2e
npm --prefix dashboard/frontend run test:e2e:integration
make smoke-test SCAN_IMAGE=seclab-sbf:full-phase156
make compose-config ENV_FILE=.env.example LAB_IMAGE=full-phase156
go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.12
make scan-image SCAN_IMAGE=seclab-sbf:full-phase156
```

UI e integración se ejecutan secuencialmente porque comparten puerto/resultados. La prueba de auditoría comprueba bloqueo en la vista previa y conserva una llamada directa de API para verificar que el backend bloquea el job sin depender de la UI. La nueva prueba revisa sin crear jobs, cambia modo/lista, rechaza revisión obsoleta y permite simular tras revisar de nuevo. Python comprueba ausencia de sockets/DNS/herramientas y escrituras, límites de presentación, pendientes y rechazo CLI de plan obsoleto; backend verifica script instalado y fallos de configuración/respuesta/timeout.

## Límites y reversión

No persiste el plan/revisión de la vista previa en el historial. No completa timeline, cadena job → evidencia → finding ni revisión humana. El wizard mantiene su simulación inicial y no incorpora esta vista previa adicional. Comandos/versiones de herramientas se inspeccionan en el avance real existente; no se implementan nuevos templates de comandos en esta fase. Un rechazo de revisión en la entrada del CLI después de crear el job conserva el comportamiento de fallo inicial sin summary, con motivo en log; clasificación diferenciada de esa carrera sigue pendiente.

Solo Chromium y Docker Desktop macOS comprobados; navegador no añadido a CI. Pruebas con datos sintéticos, usuario temporal y contenedor sin red. No se reinició el laboratorio vivo ni se cambió `seclab-sbf:full`. Revert del commit restaura el flujo previo sin migración.
