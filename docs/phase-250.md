# Fase 250 — Remediación Integral de Auditoría (Ronda 7): Banderas de Proxy de Red (B3) y Bloqueo Fail-Closed de Placeholders Mixtos No Expandidos (M4)

## Resumen Ejecutivo

- **ID de Mejora:** Auditoría de Seguridad & Robustecimiento de Salvaguardas — Ronda 7 (Blocker B3 y Major M4).
- **Objetivo:** Resolver de forma exhaustiva los hallazgos de la séptima auditoría de seguridad sobre el commit `1b9e4fc`:
  1. **B3 — Extracción y Verificación de Banderas de Proxy y Sensibilidad a Mayúsculas:**
     - En `scripts/seclab_playbook.py`, banderas como `-x` (proxy en `curl`) se agrupaban erróneamente en `FLAGS_EXPECTING_NON_TARGET_VALUE` y se normalizaban a minúsculas (`tok_clean.lower()`), haciendo que comandos como `curl -x evil.com https://target.local` ignoraran `evil.com`. Scope Guard solo evaluaba `https://target.local` y autorizaba el tráfico, llegando a invocar `subprocess.run()`.
     - **Solución implementada:**
       - Se definió `TARGET_FLAGS_WITH_VALUE` y `TARGET_FLAG_NAMES` incluyendo explícitamente `-x`, `--proxy`, `--proxy-server`, `--http-proxy`, `--https-proxy`, `--socks4`, `--socks4a`, `--socks5`, `--socks5-hostname`, `--doh-url`, `--preproxy`, `-connect`, `--connect`, `-servername`, `--servername`, `-u`, `--url`, `--target`, `--host`, `--domain`, etc.
       - Se retiró `-x` de `FLAGS_EXPECTING_NON_TARGET_VALUE` y se mantuvo `-X` (uppercase method) con comparación estrictamente sensible a mayúsculas (`tok_clean in FLAGS_EXPECTING_NON_TARGET_VALUE`).
       - Banderas como `-O` (remote-name output en `curl`) se preservan sin consumir el siguiente argumento como valor no-objetivo.
       - En `_extract_literal_targets`, tanto banderas de proxy con espacio (`curl -x evil.com`) como con asignación (`curl --proxy=evil.com` o `curl -x=evil.com`) extraen el valor del proxy hacia `tokens_to_inspect`, enviándolo a Scope Guard para bloqueo determinista si no está en alcance.
  2. **M4 — Bloqueo Fail-Closed de Placeholders de Destino Mixtos No Expandidos:**
     - En comandos activos que mezclaban un placeholder de destino sin resolver y un literal autorizado (ej. `curl https://{domain} target.local` sin parámetro `domain`), la validación estática evaluaba únicamente `target.local`, autorizaba la ejecución y corría el comando con `{domain}` sin sustituir.
     - **Solución implementada:**
       - Se introdujo `is_target_placeholder` diferenciando placeholders canónicos de destinos (`{domain}`, `{target}`, `{host}`, `{ip}`, `{proxy}`, `{url}`, `{endpoint}`, o embebidos en esquemas de red como `https://{custom}`) de claves y campos de carga útil (como `{name}` o `{__typename}` en consultas GraphQL).
       - Si cualquier paso activo contiene placeholders de destino sin expandir (`unexpanded_target_placeholders`), `validate_playbook_against_scope` marca el paso inmediatamente como `BLOCKED` con `can_execute=False`.
       - En tiempo de ejecución (`execute_playbook_step`), si un paso activo no expandió sus placeholders de destino, bloquea inmediatamente con código de salida 126 (`BLOCKED`) sin invocar bajo ninguna circunstancia a `subprocess.run()`.
       - El endpoint `/api/v1/playbooks/validate` ahora acepta y procesa `parameters` en el cuerpo JSON de la petición para permitir validar playbooks activos con parámetros legítimos en alcance.
  3. **Verificación Formal con Mocks:**
     - Pruebas unitarias con `unittest.mock.patch("subprocess.run")` certifican que ante proxies fuera de alcance o placeholders no expandidos, `subprocess.run` nunca es invocado (`mock_run.assert_not_called()`).
- **Archivos modificados:**
  - `scripts/seclab_playbook.py`: Incorporación de `TARGET_FLAGS_WITH_VALUE`, `TARGET_FLAG_NAMES`, case sensitivity en flags, función `is_target_placeholder`, y bloqueo fail-closed en `validate_playbook_against_scope` y `execute_playbook_step`.
  - `scripts/verify/test_seclab_playbook.py`: +3 nuevas pruebas unitarias (`test_b3_proxy_flags_extraction_and_blocking`, `test_b3_flag_case_sensitivity_and_non_target_flags`, `test_m4_mixed_unexpanded_placeholders_fail_closed`) alcanzando 44 pruebas en la suite.
  - `dashboard/backend/app/api/endpoints/playbooks.py`: Adición de `parameters` a `PlaybookValidateRequest` y propagación hacia `validate_playbook_against_scope`.
  - `dashboard/backend/tests/test_playbooks_api.py`: Pruebas de integración API en `/validate` para proxy no autorizado, comando mixto sin parámetro, comando mixto con parámetro autorizado y método `-X POST`.
- **Verificación:**
  - `check-python-units.py`: 351 pruebas unitarias aprobadas (+3 pruebas vs Fase 249).
  - Suite de playbooks: `test_seclab_playbook.py` con 44/44 pruebas aprobadas (+3 pruebas).
  - Pruebas semilla: `test_playbook_api_seeds.py` (6/6), `test_playbook_infra_seeds.py` (6/6) y `test_playbook_step_run.py` (2/2) aprobadas (total 58 pruebas de playbooks aprobadas).
  - Pruebas backend API: `dashboard.backend.tests.test_playbooks_api` con 2/2 suites aprobadas.
  - Frontend vitest: 193/193 pruebas aprobadas.
  - `git diff --check`: Salida limpia, cero advertencias de formato o espacios en blanco sobrantes.
