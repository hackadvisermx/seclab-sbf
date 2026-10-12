# Fase 219: Verificación de integridad criptográfica de artefactos en el compilador de reportes

Fecha: 2026-10-12 UTC. Rama `phase/219-report-artifact-verify`, base `32d07be`. V3-03cc parcial.

## Problema y cambio

El compilador de reportes (`scripts/pt-report-compiler.py`) verificaba la existencia sintáctica de los vínculos declarados en `artifact_refs`, pero no contaba con un modo estricto en CLI ni flag `--verify-artifacts` para garantizar que los artefactos referenciados en cada ficha (y el manifiesto estructurado `artifact-manifest.json`) no hubiesen sido adulterados, modificados o corrompidos en disco antes de compilar o validar el informe final.

En esta fase:
1. Compilador de reportes (`scripts/pt-report-compiler.py`):
   - Soporte para argumento opcional `verify_artifacts: bool = False` en las funciones `review_report_inputs`, `check_findings` y `build_report`.
   - Soporte para la bandera CLI `--verify-artifacts` tanto en `check` (`pt-report-compiler.py check <eng_dir> --verify-artifacts`) como en `build` (`pt-report-compiler.py build <eng_dir> [salida] --verify-artifacts`).
   - Verificación criptográfica detallada:
     - Compara los hashes SHA-256 calculados en disco de cada artefacto referenciado contra los declarados en las fichas de hallazgo.
     - Detecta discrepancias de hashes o archivos ausentes y rechaza enlaces simbólicos (`symlink`).
     - Si existe `artifact-manifest.json` (en la raíz o en `deliverables/`), ejecuta auditoría contra el manifiesto v1 reportando archivos corruptos o ausentes.
     - Bloquea la compilación (`ReportValidationError`) en caso de discrepancias o violaciones de integridad.
2. Pruebas y verificación:
   - Nuevas pruebas en `scripts/verify/test_report_safety.py`:
     - `test_verify_artifacts_flag_success`: compilación y verificación exitosa con `--verify-artifacts`.
     - `test_verify_artifacts_flag_detects_tampered_artifact`: detección inmediata de artefacto adulterado en disco bloqueando `check` y `build_report`.
   - 300 pruebas Python unitarias aprobadas en host (`check-python-units.py`).

## Verificación y límites

- 300 pruebas Python unitarias aprobadas en host.
- Pruebas de compilación segura aprobadas en `test_report_safety.py`.
- V3-03cc parcial: verificación criptográfica e integridad de artefactos en el compilador de reportes con bandera `--verify-artifacts`.
