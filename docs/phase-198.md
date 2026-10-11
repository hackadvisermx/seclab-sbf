# Fase 198: auditoría de procedencia en pt-report y export en finding-manifest v1

Fecha: 2026-10-11 UTC. Rama `phase/198-report-provenance-audit`, base `020c457`. V3-03w parcial.

## Problema y cambio

Tras la vinculación de procedencia de hallazgos introducida en la fase 197 a nivel de esquemas y sincronización del workspace, el compilador de reportes de línea de comandos (`pt-report-compiler`) y el empaquetador de entregables (`pt-engagement-packer`) aún no auditaban ni exponían los metadatos de procedencia (`source_job_id` y `source_stage`):
1. `pt-report check` y `pt-report build` no validaban el formato de `source_job_id` ni `source_stage` en los archivos de evidencia (`evidence/*.md`). Metadatos maliciosos (e.g. rutas relativas, caracteres especiales o identificadores corruptos) podían pasar sin comprobación estricta en el compilador CLI.
2. El informe final compilado (`REPORT.md`) no reflejaba formalmente el origen de ejecución (Job ID y etapa) en la sección de Detalle Técnico del hallazgo.
3. El paquete exportable de entregables generado por `pt-engagement-packer` incluye el archivo `finding-manifest.json` (schema v1), que relacionaba la identidad (`finding_id`), el archivo de origen y los artefactos, pero omitía `source_job_id` y `source_stage`.

En esta fase:
1. `scripts/pt-report-compiler.py`:
   - Importa y aplica las funciones `normalize_source_job_id` y `normalize_source_stage` de `seclab_findings`.
   - `parse_evidence_file` captura `source_job_id_raw` y `source_stage_raw`.
   - `review_report_inputs` valida ambos campos de forma estricta. Cualquier identificador inválido bloquea `check_findings` y detiene la compilación del reporte con `ReportValidationError`.
   - `build_report` traslada `source_job_id` y `source_stage` a `finding_source_output` y renderiza el campo `- **Origen de ejecución:** Job <id> (etapa: <stage>)` en la sección de Detalle Técnico del informe compilado cuando está presente.
2. `scripts/pt-engagement-packer.py`:
   - `pack_engagement` propaga `source_job_id` y `source_stage` en cada registro de `findings` en `finding-manifest.json` (v1), preservando trazabilidad completa en el entregable empaquetado y compatibilidad con fichas legacy (`null`).
3. Pruebas y verificación:
   - `scripts/verify/test_report_safety.py` ampliado para validar exportación en tar.gz y zip, sanitización, renderizado en REPORT.md, manifest v1 y bloqueo estricto ante valores malformados.

## Verificación y límites

- 251 pruebas unitarias Python en `scripts/verify/check-python-units.py` aprobadas.
- Pruebas instaladas tester/read-only/sin red de `test_report_safety.py` y `check-finding-manifest.sh` pasando.
- `make verify` y gates locales completos sin dependencias externas ni publicación.
- No firma criptográficamente el manifiesto ni reemplaza la necesidad de verificar la integridad de la base de datos de recon en el entorno de ejecución.
