# Fase 171: contexto del Copiloto ligado al estado del reconocimiento

Fecha: 2026-10-09. Rama `phase/171-context-recon-state`, base `ae39187`, worktree `/Users/castr/tmp/t01-context-state`. V3-02k/V3-05b parcial.

## Reproducción y cambio

Con un job failed persistido y un host en archivos previos, pt-next priorizaba revisar el fallo pero pt-context solo mostraba el host, sin job ni decisión pendiente. El contexto visible en el Copiloto también podía decir «Listo para cerrar» según el checklist de archivos cuando había un job bloqueado. La regresión instalada ampliada falla en full-phase170 por ausencia de recon_state. Reproducción sintética, sin red ni proyectos reales, conservada en `tmp/phase171` del checkout principal.

El módulo compartido de fase169 proyecta el último job del dashboard a un contexto mínimo: run_id, estado, etapa, modo, inicio/fin UTC, revisión vigente del resultado y siguiente decisión local. Incluye completed/simulated aunque no requieran esa decisión. No copia error, stdout, comandos, plan, targets del plan, result_summary, scope_revision ni la huella calculada sobre metadata a los campos nuevos. Se reutilizan la lectura SQLite de solo consulta, aislamiento proyecto/tipo, límites y la huella de revisión existentes. No crea DB ni migra tablas.

pt-context añade recon_state y readiness al JSON y muestra el estado al inicio del Markdown. La observación del job ocurre después de cargar archivos/checklist/skill, para incluir un job iniciado durante esa colección. Estado corrupto, bloqueado para lectura, enlazado o fecha no representable en UTC produce disponibilidad explícita no disponible y revisión local, sin detalles de la excepción. Sin job/DB o fuera del workspace configurado conserva los archivos y declara que no hay job persistido asociado.

La cobertura de archivos mantiene su puntaje, matriz y readiness original. La nueva readiness del contexto combina ese checklist con la decisión actual del job: una decisión pendiente impide mostrar «Listo para cerrar» en el contexto, sin modificar el evaluator ni las compuertas de reporte/export. El estado observado no atribuye los conteos/muestras del workspace al job; el Markdown aclara que pueden proceder de ejecuciones anteriores y usa «Servicios Web Registrados»/«JavaScript Listados».

Runner transmite WORKSPACE_DIR y SECLAB_DATA_DIR configurados al subprocess de contexto, igual que a pt-next. API de inspección y chat usan el mismo contexto; la segunda incorpora el estado al mensaje de sistema enviado al proveedor. Revisión vigente permite preparar otro plan, manteniendo estado original y sin confirmar evidencia o conceder permisos. Metadata cambiada o job nuevo invalida la revisión anterior. El modal existente presenta texto literal; no hay cambios de componentes ni controles nuevos.

## Validación

Ocho regresiones de contexto cubren todos los estados y paridad de decisión compartida, ausencia de DB/aislamiento de workspace y tipo, corrupción/estado desconocido/enlace, DB bloqueada, timestamps extremos, revisión vigente/metadata cambiada/job nuevo, job iniciado durante colección y CLI JSON/Markdown con DB sin modificar. Metadata sintética privada en error/plan/summary/scope_revision no aparece en la proyección nueva. La cobertura original se conserva aun cuando readiness contextual cambia a pendiente.

La prueba backend usa ReconJobStore real, rutas configuradas y subprocess de contexto real para todos los estados y revisión humana; comprueba la API y el mensaje recibido por un proveedor simulado, sin red. La regresión instalada de smoke compara decisiones de CLI, contexto y API como tester/read-only/network-none y preserva DB/target.yaml. Chromium con backend real/tester temporal/sin red revisa el contexto bloqueado y revisado tras recarga, junto al recorrido anterior de cinco integraciones. Capturas inspeccionadas.

Resultados: `make verify` 210 Python; `make dashboard-tests LAB_IMAGE=seclab-sbf:full-phase171 IMAGE_SOURCE=remote` 205 backend; 122 frontend/audit 0 en el build y cinco integraciones Chromium aprobadas. Build aislado, smoke/regresión instalada, Compose/Compose VPN, Actionlint 1.7.12 y gate High/Critical aprobados bajo política existente sin nuevas excepciones. Imagen `seclab-sbf:full-phase171`, build-inputs `4d87a061efe2510a`, image_id `sha256:9b831cb5d445c9ffae157ab2ba735853ee7b19444b6a6588ca0d2a43beba56f5`; etiqueta igual al hash medido. SBOM CycloneDX válido ligado al hash final, SHA-256 `9d05823065f296e18dc009154831918cfbc93379fd2c81e73fc6e3d093340f77`. Primer intento de SBOM falló por lock compartido con el escaneo; aprobado al ejecutarlo después, sin cambios de política.

Logs finales `verify-release`, `backend-release`, `build-release`, `smoke-release`, `integration-release`, `scan-release` y `sbom`, reproducción y capturas inspeccionadas en `tmp/phase171` del checkout principal. CI del head exacto requerido antes del merge.

## Compatibilidad y límites

JSON conserva coverage/recon y añade recon_state/readiness; consumidores antiguos pueden seguir usando el puntaje original, pero para la decisión contextual deben consultar readiness y recon_state. Solo se observa el último job persistido del dashboard; no registra jobs lanzados desde terminal libre, una timeline completa ni snapshots de archivos. La observación puede quedar obsoleta después y los distintos archivos no forman una lectura transaccional conjunta.

Esto aporta contexto a la IA, sin garantizar que el proveedor siga sus instrucciones ni filtrar sus propuestas según el estado del job. Proveedor/modelo conservan su contrato. El contexto no ejecuta acciones ni confirma evidencia, y no constituye una nueva frontera de ejecución/cierre del producto. La privacidad de todo el contexto, fuentes inmutables, fallback determinista y procedencia finding/job permanecen pendientes: la selección mínima se aplica a los campos nuevos, no se declara saneado el contenido previo de scope/evidence/terminal.log/skills. V3-02 y V3-05 siguen parciales.

Laboratorio vivo, proyectos del owner, etiqueta full, publicación y despliegue intactos. Fase170/PR190 quedó fusionada en ae39187 con CI 38003623117 intentos 1/2 aprobados para head b3e989b; caché restaurada y revalidada en otro runner, rama/worktree retirados. Merge de esta fase autorizado hasta 2026-10-10 14:56 UTC, con PR, diff revisado, gates y CI del head exacto aprobados.
