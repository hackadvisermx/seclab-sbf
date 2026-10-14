# Fase 254 — Remediación Integral de Auditoría (Ronda 11): Semántica de Banderas No-Objetivo por Binario (B2)

## Resumen Ejecutivo

- **ID de Mejora:** Auditoría de Seguridad & Robustecimiento de Salvaguardas — Ronda 11 (Blocker B2).
- **Objetivo:** Resolver de manera rigurosa, puntual y sin ampliaciones de alcance los hallazgos de auditoría derivados del diff de la Fase 253:
  1. **B2 — Semántica de Banderas Dependiente del Binario (`-F` en `curl` vs `nmap`):**
     - En la Fase 253, `-F` se había incorporado a `FLAGS_EXPECTING_NON_TARGET_VALUE` de forma global para admitir formularios en `curl`.
     - En `nmap`, `-F` es una bandera booleana («Fast mode») que no consume argumentos posteriores. Al procesar `nmap -F evil.com target.local`, el extractor descartaba incorrectamente `evil.com` como valor no-objetivo de `-F`, extrayendo únicamente `target.local` y autorizando indebidamente escaneos activos hacia objetivos fuera de alcance (`evil.com`).
     - **Solución implementada:**
       - **Catálogo Específico por Herramienta:** Se retiró `-F` del conjunto global `FLAGS_EXPECTING_NON_TARGET_VALUE` y se introdujo `TOOL_SPECIFIC_NON_TARGET_FLAGS: Dict[str, Set[str]] = {"curl": {"-F"}}`.
       - **Resolución Contextual de Banderas:** Se implementó `_get_non_target_flags(cmd_tpl, placeholder)` para determinar el binario invocado en el comando/segmento que contiene `{placeholder}` y resolver dinámicamente las banderas no-objetivo correspondientes.
       - **Extracción de Destinos Literales por Binario:** En `_extract_literal_targets`, se evalúa `TOOL_SPECIFIC_NON_TARGET_FLAGS.get(cmd_bin, set())`, garantizando que en `curl`, `-F` consuma el valor subsiguiente (formulario), mientras que en `nmap` se trate estrictamente como bandera booleana sin argumento, conservando y extrayendo cualquier destino posterior (`evil.com`).
       - **Salvaguarda Fail-Closed y Verificación Formal:**
         - En `curl -F file=@data.txt https://target.local` y `curl -F 'data=https://client.example/callback' https://target.local`: el payload de formulario es excluido de los objetivos y el paso resulta autorizado.
         - En `nmap -F evil.com target.local` (literal): `evil.com` es extraído y clasificado como fuera de alcance; validación estática devuelve `BLOCKED` (`can_execute=False`); ejecución directa falla cerrado con código de salida 126 (`BLOCKED`), `stop_condition_met=True` y verificación formal mediante mocks de que `subprocess.run` nunca es invocado (`mock_run.assert_not_called()`).
         - En `nmap -F {asset} target.local` (placeholder con `asset="evil.com"`): `is_target_placeholder` clasifica `{asset}` como destino de red; validación estática y dinámica bloquean con código 126 y `subprocess.run.assert_not_called()`. Control positivo con `asset="target.local"` autoriza exitosamente.
  2. **Resolución de Sugerencia Técnica (Limpieza de Bloque Inoperante):**
     - Se eliminó el bloque inoperante que invocaba `urllib.parse.urlsplit` en `_extract_literal_targets` y se removió la importación innecesaria, confiando la normalización y validación exhaustiva de URLs de destino a Scope Guard (`check_scope` / `normalize_target`), preservando la paridad con la suite de pruebas y eliminando código muerto.
- **Archivos modificados:**
  - `scripts/seclab_playbook.py`: `TOOL_SPECIFIC_NON_TARGET_FLAGS`, `_get_non_target_flags`, discriminación por binario en `is_target_placeholder` y `_extract_literal_targets`, y eliminación del bloque inoperante de `urllib.parse`.
  - `scripts/verify/test_seclab_playbook.py`: +1 nueva suite de pruebas unitarias (`test_b2_binary_specific_flags_nmap_fast_mode_vs_curl_form`), alcanzando 50 pruebas unitarias directas de playbooks.
  - `dashboard/backend/tests/test_playbooks_api.py`: +1 prueba de API dedicada (`test_playbooks_api_b2_nmap_fast_mode_blocked_vs_curl_form_authorized`), alcanzando 5 pruebas en la suite API.
- **Verificación:**
  - `check-python-units.py`: 357 pruebas unitarias aprobadas (+1 prueba vs Fase 253).
  - Suite de playbooks: `test_seclab_playbook.py` con 50/50 pruebas aprobadas (+1 prueba).
  - Pruebas semilla: `test_playbook_api_seeds.py` (6/6), `test_playbook_infra_seeds.py` (6/6) y `test_playbook_step_run.py` (2/2) aprobadas (total 64 pruebas de playbooks aprobadas).
  - Pruebas backend API: `dashboard.backend.tests.test_playbooks_api` con 5/5 pruebas aprobadas (+1 prueba).
  - Pruebas frontend: 193/193 pruebas aprobadas en Vitest.
  - `git diff --check`: Salida limpia, cero advertencias de formato o espacios en blanco sobrantes.
