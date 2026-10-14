# Fase 251 — Remediación Integral de Auditoría (Ronda 8): Banderas de Proxy Compactas y Agrupadas (B3) y Placeholders bajo Flags de Destino (M4)

## Resumen Ejecutivo

- **ID de Mejora:** Auditoría de Seguridad & Robustecimiento de Salvaguardas — Ronda 8 (Blocker B3 y Major M4).
- **Objetivo:** Resolver de manera exhaustiva y matemáticamente determinista los hallazgos de la octava auditoría de seguridad sobre el commit `c827db8` (Fase 250):
  1. **B3 — Extracción y Verificación de Proxies en Sintaxis Compacta y Agrupada:**
     - En `scripts/seclab_playbook.py`, se reconocían banderas de proxy separadas por espacio (`curl -x evil.com`) y asignadas con signo igual (`curl -x=evil.com`), pero no la sintaxis compacta válida aceptada por `curl` (`curl -xevil.com`) ni banderas agrupadas/clustered (`curl -sSxevil.com` o `curl -sSx evil.com`).
     - Esto provocaba que el token `-xevil.com` fuera descartado como bandera genérica, evaluando únicamente destinos literales posteriores (como `https://target.local`), autorizando la ejecución estática e invocando `subprocess.run()`.
     - **Solución implementada:**
       - Se introdujo `COMPACT_TARGET_SHORT_FLAGS = {"-x"}` y la función auxiliar `_flag_alternation()` para componer patrones de banderas.
       - En `_extract_literal_targets`:
         - Detección directa de banderas cortas compactas: si un token inicia con `-x` seguido directamente del valor de red sin espacio ni `=` (ej. `-xevil.com`, `-xhttp://evil.com`), se extrae el valor `evil.com` hacia `tokens_to_inspect`.
         - Detección de banderas cortas agrupadas/clustered: para tokens que inician con `-` y contienen `x` en un cluster de opciones cortas (ej. `-sSxevil.com`), se extrae el sufijo posterior a `x` como destino. Si la opción de proxy es el último carácter del cluster y viene seguida de un argumento separado (`-sSx evil.com`), se marca para inspeccionar el token siguiente.
         - Se preserva la sensibilidad a mayúsculas para no confundir `-x` (proxy) con `-X` (método HTTP).
  2. **M4 — Contrato Único para Placeholders de Destino bajo Banderas:**
     - En `scripts/seclab_playbook.py`, `is_target_placeholder` utilizaba una lista hardcodeada parcial de contextos que no compartía el contrato exhaustivo de `TARGET_FLAGS_WITH_VALUE`.
     - En comandos como `openssl s_client -connect {peer}:443 -servername target.local`, al no suministrarse el parámetro `peer`, `{peer}` no era identificado como placeholder de destino, la validación estática evaluaba únicamente `target.local`, autorizaba el paso e invocaba `subprocess.run()`.
     - **Solución implementada:**
       - Se alineó `is_target_placeholder` para inspeccionar el comando de plantilla contra todas las banderas de `TARGET_FLAGS_WITH_VALUE` (espacios, signos `=`, banderas compactas `-x{placeholder}` y clusters `-sSx{placeholder}` o `-sSx {placeholder}`).
       - Se soporta sufijos de puerto y ruta comunes en banderas de red (ej. `-connect {peer}:443` o `--proxy {p}:8080`).
       - Si el comando contiene placeholders bajo cualquiera de estas banderas y no se suministra el parámetro correspondiente, el paso activo se clasifica como `unexpanded_target_placeholders`, bloqueando tanto estáticamente (`can_execute=False`, `BLOCKED`) como en tiempo de ejecución (exit code 126, `BLOCKED`).
  3. **Verificación Formal con Mocks:**
     - Pruebas unitarias mediante `unittest.mock.patch("subprocess.run")` certifican que ante proxies compactos/agrupados fuera de alcance o placeholders no expandidos bajo flags de red, `subprocess.run` nunca es invocado (`mock_run.assert_not_called()`).
  4. **Deuda Técnica Documentada:**
     - Comandos como `curl -u user:pass https://target.local` tratan `user:pass` conservadoramente como candidato a destino (`target:port`). Al no estar en el scope, genera un bloqueo preventivo (falso positivo seguro, fail-closed). Esto no representa ninguna brecha de seguridad ni bypass del Scope Guard, por lo que se mantiene documentado como deuda técnica segura.
- **Archivos modificados:**
  - `scripts/seclab_playbook.py`: Integración de `COMPACT_TARGET_SHORT_FLAGS`, `_flag_alternation`, parsing de flags compactos y clustered en `_extract_literal_targets`, y cobertura integral de banderas en `is_target_placeholder`.
  - `scripts/verify/test_seclab_playbook.py`: +2 nuevas pruebas unitarias (`test_b3_compact_and_clustered_proxy_flags` y `test_m4_placeholders_under_target_flags_fail_closed`) alcanzando 46 pruebas en la suite.
  - `dashboard/backend/tests/test_playbooks_api.py`: Casos de prueba en `/api/v1/playbooks/validate` para proxies compactos, proxies agrupados y placeholders bajo banderas de destino (`-connect {peer}:443`).
- **Verificación:**
  - `check-python-units.py`: 353 pruebas unitarias aprobadas (+2 pruebas vs Fase 250).
  - Suite de playbooks: `test_seclab_playbook.py` con 46/46 pruebas aprobadas (+2 pruebas).
  - Pruebas semilla: `test_playbook_api_seeds.py` (6/6), `test_playbook_infra_seeds.py` (6/6) y `test_playbook_step_run.py` (2/2) aprobadas (total 60 pruebas de playbooks aprobadas).
  - Pruebas backend API: `dashboard.backend.tests.test_playbooks_api` con 2/2 suites aprobadas.
  - `git diff --check`: Salida limpia, cero advertencias de formato o espacios en blanco sobrantes.
