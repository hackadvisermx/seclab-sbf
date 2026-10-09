# Fase 157: revisión previa persistente en el historial

Fecha: 2026-10-08. Base `52f6552`, merge aprobado de #176. Rama `phase/157-recon-review-history`, worktree `/Users/castr/tmp/t01-plan-history`. Entrega parcial V3-01d/V3-02c.

## Resultado visible

Cada job iniciado con una revisión esperada muestra **Plan revisado al iniciar** en el historial. Conserva hashes de plan/alcance, hora de validación al lanzar, modo, permisos declarados, ventana, límites de sondeo, interacciones por etapa, conteos completos y muestras de hosts admitidos/descartados. Un cambio posterior de listas o alcance no reescribe esa revisión. Los targets finales pendientes del pipeline completo siguen identificados como pendientes.

La hora corresponde a la comprobación del backend al iniciar, no al primer clic del operador en la vista previa. El alcance revisado se distingue del `scope_revision` que el pipeline registra al finalizar; no se inventa este último si no existe un summary propio del run. Simular no declara ni concede permisos activos/pasivos.

Los jobs legacy o iniciados por API sin `expected_plan` muestran **Sin plan revisado registrado**. No se reconstruye la revisión desde el workspace actual ni se etiqueta una revisión nueva como si fuera antigua.

## Persistencia y datos

- Nueva tabla aditiva `recon_job_reviews`, vinculada por tipo, engagement y run_id. No cambia columnas de las tablas existentes, para mantener los INSERT posicionales de la versión anterior.
- `begin` guarda job, historial y revisión en una transacción SQLite. Si no cabe el snapshot o falla su inserción, no queda job a medio registrar ni se lanza worker. Máximo de payload: 192 KiB; muestras de 50 targets y 50 descartes por etapa.
- La API de historial devuelve `reviewed_plan` v1 o null. El contrato del job actual permanece igual. Cancelación, finalización, recuperación de sesión y backup SQLite conservan la revisión inicial; `finish` no la sustituye por resultados.
- El borrado/restauración existente del proyecto elimina sus revisiones. Al reabrir una base modificada por una versión anterior, se retiran snapshots sin fila de historial; la versión anterior no conoce esta tabla.
- Snapshot guarda solo host de cada target, incluyendo IPv6. Omite userinfo, rutas, consultas, fragmentos, mensajes libres del matcher y referencia textual de autorización. Conserva presencia de referencia, permisos/fechas validados, verdict y conteos. Distintas URLs pueden mostrar el mismo host; el conteo no se deduplica por esa representación.
- Bases de consulta pasiva se marcan `PASSIVE_SOURCE`, no `IN_SCOPE`: derivar un apex de wildcard para consultar fuentes externas no autoriza tráfico activo contra ese apex.
- La vista previa CLI/API añade los campos estructurados de autorización sin su referencia textual. Las compuertas de alcance/permisos y `expected_plan` se mantienen. Una revisión incompleta se rechaza antes de crear un job.

Los metadatos siguen siendo información del proyecto en una base local con permisos 600; no se envían a analítica externa. No se recopilan comandos ni stdout en esta tabla. La proyección a hosts reduce exposición, no anonimiza el engagement ni inspecciona todo secreto posible dentro de un hostname.

## Verificación

- `make verify`: 175 pruebas Python aprobadas.
- Backend: 156 pruebas aprobadas en imagen nativa, incluidos snapshot antes de worker, persistencia con cambios de inputs/scope, backup/reinicio/cancelación, rollback atómico por error SQL, límite de tamaño, aislamiento y compatibilidad de INSERT legacy.
- Frontend: 103 pruebas aprobadas; audit 0 vulnerabilidades.
- Chromium: 2 pruebas UI y 3 integraciones reales aprobadas, ejecutadas secuencialmente. La integración de reconocimiento simula con `expected_plan`, cambia la lista local, recarga y confirma que el historial conserva hash/hosts/permisos originales. Screenshot `review-history.png` inspeccionado; artefactos de Playwright ignorados.
- Imagen aislada `seclab-sbf:full-phase157`, hash de insumos `ff26708e27bf2cf0`, coincide con el checkout. Build, smoke, Compose `.env.example`, Actionlint y gate High/Critical aprobados bajo política vigente, sin nuevas dependencias ni excepciones.
- No quedan contenedores `seclab-playwright-*` ni credenciales temporales. No se modificaron proyectos del owner, imagen `seclab-sbf:full` ni laboratorio vivo.

```sh
make verify
make build-full BUILD_TAG=-phase157
make dashboard-tests LAB_IMAGE=full-phase157 IMAGE_SOURCE=remote
npm --prefix dashboard/frontend test
npm --prefix dashboard/frontend run audit
npm --prefix dashboard/frontend run test:e2e
npm --prefix dashboard/frontend run test:e2e:integration
make smoke-test SCAN_IMAGE=seclab-sbf:full-phase157
make compose-config ENV_FILE=.env.example LAB_IMAGE=full-phase157
go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.12
make scan-image SCAN_IMAGE=seclab-sbf:full-phase157
```

Un primer pase de backend detectó un error de cleanup del nuevo fixture: se intentaba hacer join de un hilo cuyo start estaba simulado. Se corrigió la limpieza de esos hilos de prueba; no se modificó el shutdown real ni se relajaron aserciones. Suites finales aprobadas. El build se repitió después de los últimos cambios de pruebas para verificar el hash exacto.

## Límites, autorización y reversión

No es todavía una timeline de decisiones de todo el engagement, ni la cadena job → artefacto → evidencia → finding. La muestra de hosts no conserva identidad exacta de URLs; el hash de plan sí representa las entradas originales, pero no las recupera. No copia outputs antiguos ni congela DNS/inputs/descubrimientos durante el job. Una revisión guardada no autoriza replay; nuevas ejecuciones siguen revalidándose. Terminal libre fuera de Scope Guard. Clasificación de rechazo inicial del CLI sin summary permanece pendiente.

Solo Chromium y Docker Desktop macOS comprobados. Revert del commit hace que la versión previa ignore la tabla adicional y conserva compatibilidad de sus tablas; para eliminar físicamente metadatos tras revert se requiere tratamiento explícito de la base, no se borra automáticamente información histórica. Si una versión anterior borra proyectos, las revisiones huérfanas se limpian al volver a esta versión.

El owner autoriza merges sin preguntar durante 24 horas del 2026-10-08 19:09:04 UTC al 2026-10-09 19:09:04 UTC, manteniendo PR, gates y CI del head exacto. PR #177 fusionado en `a24fa16` con esa autorización y CI `37831338183` aprobado; rama/worktree retirados. Al vencer la ventana vuelve la aprobación individual. Esa autorización no habilita publicar imágenes ni reiniciar el laboratorio vivo.
