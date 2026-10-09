# Fase 163: resultados conservados por job de reconocimiento

Fecha: 2026-10-09. Rama `phase/163-recon-result-history`, base `999ae81`, worktree `/Users/castr/tmp/t01-result-history`. Entrega parcial V3-02e.

## Problema comprobado y cambio

La reproducción aislada en `full-phase162` terminó dos jobs con conteos de URLs 1 y 3: el workspace conservaba 3 y el historial solo los estados de ambos, sin resultados históricos. Ahora el worker guarda un resumen acotado del resultado al finalizar, ligado a proyecto/tipo/run_id, etapa seleccionada y revisión de alcance. La API autenticada de historial añade `result_summary`; los contratos del job actual y CLI no cambian.

`app/core/recon_results.py` conserva siete conteos del workspace, timestamp UTC, fuente de métricas y hasta cuatro etapas en orden canónico. De cada etapa conserva estado, clase de fallo y conteos permitidos; para patrones, solo los siete nombres conocidos y sus conteos. No copia targets, URLs, paths, comandos, errores, contrato completo ni referencia de autorización al nuevo resumen. Los errores del job siguen en su campo existente.

Se acepta solo un summary textual completo de hasta 2 MiB de contenido, correspondiente al run_id actual, con schema/campos y estados consistentes con el resultado del proceso. La lectura reutiliza el lector por descriptores de fase160: no sigue enlaces y rechaza cambios detectados; su límite general de lectura/hash es 32 MiB. Scope y resultados se toman de la misma lectura. Resumen antiguo, incompleto, inválido, discrepancia de estado, simulación, cancelación, interrupción o fallo inicial sin summary no inventan resultados. El job conserva su clasificación aunque no haya un resumen aceptable.

La tabla aditiva `recon_job_results` conserva el JSON validado con máximo 16 KiB por job. Estado final, historial y resultado se escriben en una transacción. Una finalización tardía no sobrescribe un resultado previo. Lectura revalida JSON contra el job y ofrece `null` si fue corrompido o es incompatible; no reconstruye números desde archivos actuales. Backups SQLite incluyen la tabla y borrar/restaurar un proyecto limpia solo sus resultados, como su historial. No migra conteos de jobs legacy.

La UI abre “Resultados conservados al terminar” por job. Los conteos globales se rotulan como workspace al terminar, porque pueden contener artefactos de etapas no ejecutadas en ese job. Ante fallo/bloqueo, `previous_artifacts` advierte que no acredita resultados nuevos. Los conteos propios de etapas completadas permanecen distinguibles; un patrón no confirma vulnerabilidades. Simulaciones y registros sin summary indican su ausencia. Los outputs originales continúan en el workspace y pueden reemplazarse en ejecuciones posteriores.

## Verificación

```sh
make verify
make build-full BUILD_TAG=-phase163
make dashboard-tests LAB_IMAGE=full-phase163 IMAGE_SOURCE=remote
npm --prefix dashboard/frontend test
npm --prefix dashboard/frontend run audit
npm --prefix dashboard/frontend run test:e2e:integration
npm --prefix dashboard/frontend run test:e2e
make smoke-test SCAN_IMAGE=seclab-sbf:full-phase163
make compose-config ENV_FILE=.env.example LAB_IMAGE=full-phase163
go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.12
make scan-image SCAN_IMAGE=seclab-sbf:full-phase163
```

- `make verify`: 183 Python; backend 188; frontend 113; audit 0. Las ocho pruebas nuevas de backend cubren persistencia/backup, filtrado de datos privados, schema inválido, orden/parsers de etapas, discrepancias de run/estado, métricas previas, ausencia de resultados legacy/simulados, corrupción, borrado aislado, atomicidad y finalizaciones tardías.
- 3 UI y 5 integraciones Chromium aprobadas con tester temporal y `--network none`. La integración extendida usa lista vacía (sin sockets/DNS) para dos sondeos con conteos 1/3, agrega bloqueo sin permiso, recarga y verifica cada resumen. Captura `result-history.png` inspeccionada; fixture/credenciales eliminados al terminar.
- Imagen aislada `seclab-sbf:full-phase163`, hash final de insumos `13d30a69d351851e`, idéntico al checkout. Build, smoke, Compose con `.env.example`, Actionlint y gate CVE High/Critical aprobados bajo política vigente; sin nuevas dependencias ni excepciones.
- Integración en [PR #183](https://github.com/hackadvisermx/seclab-sbf/pull/183) hacia `bootstrap/baseline`; estado y evidencia de CI del head exacto registrados en el PR. Merge requiere gates y CI aprobados durante la autorización temporal.

## Límites y reversión

Es un resumen del pipeline controlado, sin firma ni garantía frente a edición manual por el operador. No guarda snapshots de bytes ni outputs anteriores, no vincula un finding a un job ni identifica herramientas/versiones. No registra jobs de terminal libre ni completa la timeline del engagement. Contadores globales no equivalen a resultados nuevos de todas las etapas ni cobertura de vulnerabilidades.

Revert puede ignorar la tabla aditiva sin perder los archivos del workspace; no añade columnas que rompan INSERT legacy ni introduce nuevas dependencias. No cambia permisos, matcher ni ejecución de herramientas. Laboratorio vivo, proyectos e imagen full del owner intactos. Merge sujeto a PR, gates y CI aprobado del head exacto durante la autorización temporal de AGENTS.md.

## Cierre confirmado

PR #183 fusionado en `c221db38edc7765953b01548de376396e2462f30` el 2026-10-09 12:29:02 UTC, dentro de la autorización temporal del owner. CI `37929820943` aprobado para head exacto `cb0a2db7d3af963cee20fc8aa7fc2d8de620b1ad`. Baseline sincronizado y rama/worktree retirados; evidencia en `tmp/phase163` del checkout principal.
