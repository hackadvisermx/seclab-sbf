# Fase 197: procedencia de hallazgos (job y etapa de origen)

Fecha: 2026-10-11 UTC. Rama `phase/197-finding-job-origin`, base `bca6967`. V3-03v parcial.

## Problema y cambio

Hasta la fase 196, una ficha de hallazgo (`finding`) contenía identidad (`finding_id`), referencias de artefactos (`artifact_refs`), estado, severidad y justificación de confirmación humana, pero carecía de trazabilidad formal hacia el trabajo de reconocimiento (`recon_job`) y etapa (`stage`) que originó o respaldó el hallazgo. Si un hallazgo declaraba un `source_job_id` o `source_stage`, estos campos no eran validados, ni preservados de forma estructurada en la API, ni verificados contra el historial persistido de trabajos.

En esta fase:
1. `scripts/seclab_findings.py` incorpora funciones de normalización y validación estricta:
   - `normalize_source_job_id`: exige un identificador `run_id` hexadecimal de 32 caracteres (o `None`).
   - `normalize_source_stage`: valida un identificador alfanumérico seguro de etapa (hasta 64 caracteres, o `None`).
   - `parse_finding_frontmatter` valida tanto con PyYAML como sin él que `source_job_id` y `source_stage` sean tipos escalares textuales válidos.
2. Los esquemas Pydantic del backend (`FindingFrontmatter`, `FindingDetail`, `FindingCreate`) incorporan `source_job_id`, `source_stage` y el campo de diagnóstico de solo lectura `source_job_error`.
3. `workspace_sync.py` valida la procedencia al sincronizar o guardar hallazgos:
   - Si se declara `source_job_id`, verifica su existencia en `recon_job_history`.
   - Si se declara `source_stage`, verifica que el job contenga dicha etapa completada en su resumen.
   - Si la ficha declara artefactos (`artifact_refs`), valida que los hashes SHA-256 de los artefactos coincidan con los registrados en la ejecución de dicho job (`recon_job_results`), detectando discrepancias o manipulaciones posteriores.
   - Cualquier inconsistencia se reporta en `source_job_error` (`job_not_found`, `stage_not_in_job`, `stage_not_completed`, `artifact_hash_mismatch`) sin corromper el contenido original ni inventar atribuciones.
4. En el dashboard (`EngagementDetailView.vue`), el detalle del hallazgo muestra una sección de Procedencia de Reconocimiento y el modal de edición permite consultar y asignar de forma segura el Job y Etapa de origen.

## Verificación y límites

- Backend: 7 pruebas unitarias nuevas en `dashboard/backend/tests/test_finding_provenance.py` validan:
  - Registro de procedencia válida con match de artefactos.
  - Reporte de error cuando el job no existe en el historial.
  - Reporte de error cuando la etapa no corresponde o no está completada.
  - Detección de alteración de artefactos respecto a los producidos en el job.
  - Soporte de fichas legacy sin procedencia (no emite error espurio).
  - Rechazo de identificadores y etapas con formato malicioso o inválido en la API.
- Frontend: 156 pruebas unitarias (`npm test`) pasando al 100%.
- Python unit tests: 250 pruebas aprobadas en `check-python-units.py`.
- Esta fase no audita aún la procedencia dentro del compilador CLI de reportes (`pt-report`) ni exporta el árbol de procedencia en `finding-manifest v1` (objetivo de Fase 198).
