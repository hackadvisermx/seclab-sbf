# Fase 247 — Remediación Integral de Auditoría (Ronda 4): Cierre de Destinos Literales (B3), Fixtures Semilla (M3) e Integración al Gate Global

## Resumen Ejecutivo

- **ID de Mejora:** Auditoría de Seguridad & Robustecimiento de Salvaguardas — Ronda 4 (Blocker B3, Major M3 y Endurecimiento).
- **Objetivo:** Resolver de forma exhaustiva y definitiva los hallazgos señalados en la cuarta auditoría de seguridad sobre el commit `3159e02`:
  1. Bloquear pasos activos en playbooks con destinos literales no vinculados a `target_selector` (ej. `curl https://destino-fuera-de-alcance`) o sin destinos declarables ni resolubles (ej. `printf 'EXECUTED'`).
  2. Subsanar la regresión en las pruebas de playbooks semilla (`test_playbook_api_seeds.py` y `test_playbook_infra_seeds.py`) incorporando contratos canónicos de alcance (`scope:`) compatibles con la validación estricta de la Fase 246.
  3. Eliminar el fallback permisivo ante imposibilidad de importar `seclab_scope` implementando una política universal fail-closed.
  4. Incorporar las 14 pruebas unitarias de playbooks semilla y ejecución de pasos al gate global `check-python-units.py`.
- **Hallazgos Resueltos:**
  - **B3 (Blocker - Destinos literales sin vínculo obligatorio con Scope Guard):**
    - En `scripts/seclab_playbook.py` (`extract_step_targets`): se incorporó la extracción exhaustiva de destinos literales en `command_template`:
      - URLs completas con esquema `http://` o `https://` sin placeholders no expandidos.
      - Direcciones IP literales (IPv4 e IPv6 estándar y en corchetes), descartando flags operacionales como servidores DNS resolver `@1.1.1.1`.
      - FQDNs / dominios literales con sintaxis válida, descartando extensiones de archivo operacionales (`.txt`, `.py`, `.sh`, `.yaml`, etc.).
    - En `scripts/seclab_playbook.py` (`step_has_declared_target_source` y `validate_playbook_against_scope`): todo paso activo (`active_low`, `active_high`, o con permiso `active`) debe declarar una fuente de destino resoluble; pasos sin fuentes ni objetivos son bloqueados preventivamente. Si se extraen destinos literales, se evalúan obligatoriamente contra `check_scope`.
    - En `scripts/seclab_playbook.py` (`execute_playbook_step`): en ejecución real (`not dry_run`), ningún paso activo puede ejecutarse sin al menos un destino candidato verificado como `IN_SCOPE` por Scope Guard. La falta de destinos candidatos o destinos fuera de alcance detiene la ejecución inmediatamente con código de salida 126 y estado `BLOCKED`.
  - **M3 (Major - Regresión en pruebas de playbooks semilla):**
    - Se actualizaron los fixtures de prueba en `scripts/verify/test_playbook_api_seeds.py` y `scripts/verify/test_playbook_infra_seeds.py` con una sección `scope:` canónica y válida, junto con parámetros acordes a los placeholders de las plantillas (`domain` y `target`), logrando la aprobación al 100% de las pruebas semilla sin relajar las salvaguardas fail-closed.
  - **Endurecimiento Fail-Closed:**
    - Si el módulo `seclab_scope` no puede ser importado en `validate_playbook_against_scope` o `execute_playbook_step`, la validación y ejecución fallan cerrado de inmediato (`BLOCKED`, código 126).
  - **Integración al Gate Global de Pruebas:**
    - Se integraron `test_playbook_api_seeds.py` (6 pruebas), `test_playbook_infra_seeds.py` (6 pruebas) y `test_playbook_step_run.py` (2 pruebas) en `scripts/verify/check-python-units.py`, elevando la cobertura del gate a 340 pruebas unitarias aprobadas.
- **Archivos modificados:**
  - `scripts/seclab_playbook.py`: Extracción de destinos literales en `extract_step_targets`, función `step_has_declared_target_source`, validación fail-closed estricta de destinos para pasos activos y disponibilidad de `check_scope`.
  - `scripts/verify/test_playbook_api_seeds.py`: Inclusión de `scope_yaml` y parámetros en las pruebas de playbooks de APIs.
  - `scripts/verify/test_playbook_infra_seeds.py`: Inclusión de `scope_yaml` y parámetros en las pruebas de playbooks de infraestructura.
  - `scripts/verify/test_seclab_playbook.py`: 3 nuevas pruebas unitarias para destinos literales fuera de alcance, en alcance y comandos sin destino, además del ajuste en el template del selector sin parámetros.
  - `scripts/verify/check-python-units.py`: Carga y ejecución automática de las suites de plantillas semilla y ejecución paso a paso.
- **Verificación:**
  - `check-python-units.py`: 340 pruebas unitarias aprobadas (+17 pruebas vs Fase 246).
  - Pruebas semilla individuales: `test_playbook_api_seeds.py` (6/6), `test_playbook_infra_seeds.py` (6/6), `test_playbook_step_run.py` (2/2) aprobadas.
  - Suite de playbooks: `test_seclab_playbook.py` con 33/33 pruebas aprobadas.
  - Pruebas backend API: `tests.test_playbooks_api` con 2/2 pruebas aprobadas.
  - Pruebas frontend: 193 pruebas en Vitest aprobadas sin fallos.
  - `git diff --check`: Salida limpia, cero advertencias de formato o trailing whitespace.
