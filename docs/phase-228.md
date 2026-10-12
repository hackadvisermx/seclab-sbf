# Fase 228 — Ingestión y Trazabilidad de Corridas CLI Externas en recon_jobs.db (V3-02r)

## Contexto y Motivación
En ejercicios de pruebas de penetración y auditorías operacionales, los operadores frecuentemente ejecutan herramientas de línea de comandos de forma manual o interactiva (e.g. `nmap`, `subfinder`, `httpx`, `ffuf`, scripts ad-hoc en terminal libre). Tradicionalmente, estas actividades no quedaban vinculadas al registro histórico estructurado de `recon_jobs.db`, dejando vacíos de procedencia en la trazabilidad de hallazgos y en la supervisión metodológica.

La iniciativa V3-02 estipula que toda actividad operativa relevante debe poder registrarse en el historial formal del proyecto, distinguiendo claramente su origen (`cli-external` vs pipelines automatizados del dashboard).

## Cambios Implementados

1. **Módulo CLI y Utilidad (`scripts/seclab_record_job.py`)**:
   - Función `record_external_recon_job(...)` y CLI con argumentos `--engagement`, `--tool`, `--stage`, `--command`, `--status`, `--notes` y `--db`.
   - Inserta registros de auditoría en la tabla `recon_job_history` con `origin = 'cli-external'`, `dry_run = 0` y detalles del comando en el registro de información.

2. **Servicio Backend (`dashboard/backend/app/services/recon_service.py`)**:
   - Método `record_external_job(...)` integrado en `ReconService`.

3. **Backend FastAPI (`dashboard/backend/app/api/endpoints/recon.py`)**:
   - Endpoint `POST /api/v1/recon/{id}/record-external-job` con validación Pydantic estricta (`ExternalJobRecordRequest`).

4. **Cliente Frontend (`dashboard/frontend/src/api.js`)**:
   - Método `api.recordExternalReconJob(id, data, type)`.

5. **Interfaz Dashboard (`dashboard/frontend/src/views/EngagementDetailView.vue`)**:
   - Botón «+ Ingestar Corrida CLI» (`data-testid="record-external-job-btn"`) en el encabezado del historial de reconocimiento.
   - Modal táctico accesible (`data-testid="record-external-job-modal"`) con formulario para herramienta, comando, etapa, estado y notas, y botón de confirmación (`data-testid="submit-external-job-btn"`).
   - Insignia cromática `CLI_EXTERNAL` (`data-testid="cli-external-badge"`) en cada registro del historial originado por comandos manuales.

6. **Pruebas y Verificación**:
   - Pruebas unitarias de persistencia en SQLite (`scripts/verify/test_record_external_job.py`).
   - Pruebas frontend en Vitest (`dashboard/frontend/tests/external-recon-job.test.js`, build Vite limpio).
