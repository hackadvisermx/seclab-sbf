# Fase 253 — Remediación Integral de Auditoría (Ronda 10): Precedencia Sintáctica de Destinos (B1) y Preservación de Contexto No-Objetivo Postinterpolación (M1)

## Resumen Ejecutivo

- **ID de Mejora:** Auditoría de Seguridad & Robustecimiento de Salvaguardas — Ronda 10 (Blocker B1 & Major M1).
- **Objetivo:** Resolver de manera rigurosa y puntual los hallazgos de auditoría derivados del diff 1bd36ce..7235e91:
  1. **B1 — Prevalencia de Banderas de Destino sobre Exclusiones por Nombre y FQDN con Punto Terminal:**
     - En `scripts/seclab_playbook.py`, `is_target_placeholder` evaluaba `NON_TARGET_PLACEHOLDERS` (`method`, `methods`, etc.) antes que `TARGET_FLAGS_WITH_VALUE`. Por consiguiente, ante `curl --proxy {method} https://target.local` con `method="evil.com."`, el placeholder era clasificado como no-objetivo. Además, el extractor posterior no admitía la notación canónica DNS con punto terminal (`evil.com.`), permitiendo que el paso fuera autorizado y se ejecutara `subprocess.run()`.
     - **Solución implementada:**
       - **Regla de Precedencia Estricta:** La posición sintáctica inequívoca de destino (`target_patterns`, incluyendo `--proxy`, `-x`, `--url`, `-connect`, esquemas URI `://{p}`, etc.) se evalúa en primer lugar y prevalece sobre cualquier nombre o exclusión en `NON_TARGET_PLACEHOLDERS`.
       - **Soporte FQDN con Punto Terminal DNS:** `_extract_literal_targets`, `extract_step_targets` y `is_target_placeholder` reconocen, extraen y normalizan dominios con notación de raíz DNS (`evil.com.` -> `evil.com.` y `evil.com`), evaluándolos contra Scope Guard.
       - **Salvaguarda Fail-Closed y Verificación Formal:** Validación estática devuelve `BLOCKED` (`can_execute=False`) ante destinos de proxy fuera de alcance o placeholders sin resolver; ejecución directa devuelve código 126 (`BLOCKED`) con `stop_condition_met=True` y verificación formal con mocks de que `subprocess.run` nunca es invocado (`mock_run.assert_not_called()`).
  2. **M1 — Preservación de Contexto Argumental y Exclusión de URLs en Cargas Útiles:**
     - Al analizar el comando postinterpolación, `_extract_literal_targets` realizaba un escaneo global vía expresión regular sobre todo el comando, capturando URLs ubicadas dentro de banderas de datos u operacionales (ej. `curl -d '{payload}' https://target.local` con `payload="https://client.example/callback"`), perdiendo el contexto de `-d`, `-H`, `--data`, etc., y bloqueando erróneamente pasos autorizados de playbooks API/OAuth.
     - **Solución implementada:**
       - **Extracción Consciente de Argumentos:** Se eliminó el escaneo global de URIs sobre la cadena completa. La extracción de URIs ahora opera exclusivamente sobre los tokens que no han sido consumidos por banderas que esperan valores no-objetivo (`FLAGS_EXPECTING_NON_TARGET_VALUE`, ampliadas con `--json`, `--data-urlencode`, `--data-ascii`, `-F`, `--form`, `-e`, `--referer`, `--post-data`).
       - **Control de Seguridad Bidireccional:** Un payload que contiene una URL externa bajo `-d` o `-H` es autorizado sin agregar falsos objetivos de red; paralelamente, la misma URL externa cuando aparece como destino real (`curl https://client.example/callback`) es bloqueada de inmediato tanto en validación como en ejecución.
  3. **Sugerencias Resueltas:**
     - **Separación de Pruebas API:** Se crearon métodos de prueba individuales en `test_playbooks_api.py` (`test_playbooks_api_b1_target_flag_precedence_over_non_target_name` y `test_playbooks_api_m1_non_target_payload_url_authorized`) para asegurar diagnóstico granular e inequívoco de invariantes ante regresiones.
     - **Documentación de Precedencia:** Se documentó formalmente en el docstring de `is_target_placeholder` que la posición sintáctica de destino prevalece invariablemente sobre el nombre del placeholder.
- **Archivos modificados:**
  - `scripts/seclab_playbook.py`: Regla de precedencia sintáctica en `is_target_placeholder`, eliminación de escaneo global en `_extract_literal_targets`, extracción de URIs respetando contexto operacional, y soporte de FQDNs con punto terminal DNS.
  - `scripts/verify/test_seclab_playbook.py`: +2 nuevas pruebas unitarias (`test_b1_target_flag_precedence_over_non_target_name_and_trailing_dot_fqdn` y `test_m1_non_target_payload_url_exclusion_and_context_preservation`), alcanzando 49 pruebas en la suite.
  - `dashboard/backend/tests/test_playbooks_api.py`: +2 métodos de prueba de API dedicados para validación de B1 y M1.
- **Verificación:**
  - `check-python-units.py`: 356 pruebas unitarias aprobadas (+2 pruebas vs Fase 252).
  - Suite de playbooks: `test_seclab_playbook.py` con 49/49 pruebas aprobadas (+2 pruebas).
  - Pruebas semilla: `test_playbook_api_seeds.py` (6/6), `test_playbook_infra_seeds.py` (6/6) y `test_playbook_step_run.py` (2/2) aprobadas (total 63 pruebas de playbooks aprobadas).
  - Pruebas backend API: `dashboard.backend.tests.test_playbooks_api` con 4/4 pruebas aprobadas (+2 pruebas).
  - Pruebas frontend: 193/193 pruebas aprobadas en Vitest.
  - `git diff --check`: Salida limpia, cero advertencias de formato o espacios en blanco sobrantes.
