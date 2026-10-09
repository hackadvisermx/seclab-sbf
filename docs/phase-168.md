# Fase 168: revisión persistente del resultado de reconocimiento

Fecha: 2026-10-09. Rama `phase/168-recon-outcome-review`, base `5a057d0`, worktree `/Users/castr/tmp/t01-outcome-review`. V3-02i parcial.

## Situación comprobada

La fase166 conserva fallo/bloqueo/cancelación/interrupción y dirige a revisar el job, pero no registra que el operador ya hizo esa revisión. La reproducción contra su imagen instalada, como tester/read-only/sin red, devuelve `recon_blocked`, POST review HTTP 405 y ningún campo de revisión en el historial. El 405 procede del router SPA GET cuando no existe el endpoint POST; no es un fallo del matcher. Evidencia en `tmp/phase168/reproduction.log` del checkout principal.

## Cambio y contrato

- Tabla aditiva `recon_job_outcome_reviews`, aislada por tipo/proyecto/run_id, timestamp UTC y huella SHA-256 de metadata persistida. Mantiene las nueve columnas de `recon_jobs` y compatibilidad con lectores/escritores anteriores. Backup SQLite y eliminación por proyecto incluyen el registro; reabrir reconcilia legacy y elimina registros huérfanos.
- La huella cubre identidad, estado, etapa/modo, inicio/fin, motivo, revisión de scope, plan y resumen almacenados. No guarda copias nuevas de URLs, comandos, stdout, secretos o motivo libre. Un cambio de metadata invalida la revisión; un downgrade que devuelve el job a ejecución tampoco muestra una revisión vigente. No es firma ni prueba de lectura humana o integridad de artefactos.
- POST autenticado `/api/v1/recon/{id}/review` acepta únicamente run_id y expected_revision. En transacción BEGIN IMMEDIATE comprueba el último job terminal y la versión vista; job nuevo/activo/ajeno/obsoleto devuelve 409. Una solicitud idéntica conserva el timestamp inicial. No lanza herramientas, cambia target.yaml ni modifica estado/resumen original.
- La UI exige una decisión explícita para preparar otro plan y muestra la revisión separada del plan validado al iniciar. Tras registrar esa decisión en cualquier estado terminal, la decisión `recon_prepare_plan` lleva a Reconocimiento, sin comando ni prompt. Running/cancelling siguen esperando y no admiten revisión. Completed/simulated sin esa decisión explícita conservan el contrato previo de siguiente paso.
- Registrar revisión invalida el preview anterior. El nuevo preview y lanzamiento conservan las compuertas de alcance/permisos. Respuestas tardías de revisión/estado de otro proyecto o del componente desmontado se descartan; errores no simulan éxito y exigen volver a marcar la decisión.

## Validación

```sh
make verify
make build-full BUILD_TAG=-phase168
make dashboard-tests LAB_IMAGE=full-phase168 IMAGE_SOURCE=remote
npm --prefix dashboard/frontend test
npm --prefix dashboard/frontend run audit
npm --prefix dashboard/frontend run test:e2e
PLAYWRIGHT_LAB_IMAGE=seclab-sbf:full-phase168 npm --prefix dashboard/frontend run test:e2e:integration
make smoke-test SCAN_IMAGE=seclab-sbf:full-phase168
make compose-config ENV_FILE=.env.example LAB_IMAGE=full-phase168
go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.12
make scan-image SCAN_IMAGE=seclab-sbf:full-phase168
make sbom SCAN_IMAGE=seclab-sbf:full-phase168
```

186 Python, 203 backend, 122 frontend, audit 0; 3 UI y 5 integraciones Chromium aprobados. Build aislado `seclab-sbf:full-phase168`, hash `04321d3e77f9ae35` igual al checkout. Smoke/Compose/Actionlint y gate High/Critical aprobados bajo política existente, sin nuevas excepciones/dependencias. SBOM CycloneDX válido ligado al hash final, SHA-256 `0fff8c2f3a9ccc3bc2341968202fd40adf8a09fa24d05d753e01c6ed2706247f`.

Pruebas en `dashboard/backend/tests/test_recon_outcome_review.py`: estados terminales, idempotencia, reinicio/backup, API/auth/inputs/error sanitizado, aislamiento incluso con run_id igual, revisión concurrente con inicio de job, metadata cambiada y downgrade. Vue comprueba decisión explícita, rechazo, job activo/obsoleto y respuestas tardías de otro proyecto. El caso instalado `recon-preview.spec.js` revisa un bloqueo, recarga, conserva estado/conteos/target.yaml y cantidad de jobs, cambia la siguiente decisión y demuestra que un plan activo sigue bloqueado por falta de permiso. Capturas `outcome-review-history.png`/`outcome-review-decision.png` inspeccionadas y conservadas en `tmp/phase168` del checkout principal. Tester/fixtures temporales eliminados.

## Compatibilidad, límites y operación

Revisión declarada por el operador único; no registra identidad multiusuario ni rationale libre ni firma. Conserva una revisión vigente por job; nuevos jobs mantienen la revisión anterior en historial, pero revisarla ahora no cambia la decisión del job nuevo. No acepta resultados parciales ni cambia heurística de cobertura/readiness. Los archivos/logs vivos no forman parte de esta huella. CLI directo mantiene su comportamiento anterior; no completa timeline global, procedencia finding/job ni aceptación probatoria. V3-02 sigue parcial.

Revert de código ignora la tabla aditiva; reabrir la nueva versión vuelve a validar la huella contra metadata actual. Una corrección administrativa y nueva revisión puede sustituir el registro invalidado; no es un log inmutable. Laboratorio vivo, proyectos del owner, etiqueta full y publicación/despliegue intactos.

Cada entrega pasa por PR hacia bootstrap/baseline, revisión del diff, gates y CI del head exacto; autorización vigente hasta 2026-10-10 14:56 UTC. Estado de merge de fase166 reconciliado sin crear otra fase funcional.
