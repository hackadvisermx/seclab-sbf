# Fase 249 — Remediación Integral de Auditoría (Ronda 6): Extracción de Hosts de una Sola Etiqueta (B3 & M6) y Validación Estática Fail-Closed de Placeholders (M4)

## Resumen Ejecutivo

- **ID de Mejora:** Auditoría de Seguridad & Robustecimiento de Salvaguardas — Ronda 6 (Blocker B3, Major M4 y Major M6).
- **Objetivo:** Resolver de forma exhaustiva los hallazgos de la sexta auditoría de seguridad sobre el commit `6e0ce0b`:
  1. **B3 & M6 — Extracción sintáctica contextual de hosts de una sola etiqueta y prevención de exclusiones globales:**
     - `_extract_literal_targets` en `scripts/seclab_playbook.py` exigía la presencia obligatoria de un punto (`.`) en el nombre de host, omitiendo destinos válidos de una sola etiqueta como `localhost`, `db` o `service`.
     - Además, una exclusión global por listas planas de palabras clave podía descartar erróneamente tokens en posición de argumento que coincidieran con palabras comunes (`test`, `get`, `query`, `true`, `false`).
     - **Solución implementada:** Se reestructuró `_extract_literal_targets` para aplicar un análisis sintáctico basado en el contexto de la shell:
       - Segmentación de comandos por operadores de control de shell (`;`, `|`, `&&`, `||`).
       - El primer token de cada segmento se identifica como binario ejecutable y nunca es catalogado como destino.
       - Procesamiento y omisión de argumentos consumidos por banderas operacionales (`-X`, `-H`, `-o`, `-oN`, `-w`, `--script`, `-mc`, `-p`, `-l`, etc.).
       - Filtrado de operadores de redirección (`>`, `>>`, `<`).
       - Detección de subcomandos de herramientas estándar (`openssl s_client`, `ip neighbor show`, `dig ANY/axfr`).
       - Extracción rigurosa de cualquier token en posición de argumento que cumpla con la sintaxis de host RFC 1123 (`[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?`), incluyendo `localhost`, `db`, `service`, `test`, `get`, `query`, `true`, `false`, remitiéndolos obligatoriamente a Scope Guard.
       - Si el destino no está explícitamente listado en `in_scope`, Scope Guard dictamina `UNKNOWN` y bloquea la ejecución estática y real con código 126.
  2. **M4 — Paridad fail-closed estática ante placeholders de destino sin parámetros:**
     - En `validate_playbook_against_scope`, la verificación `and not unexpanded_target_placeholders` permitía que pasos activos con placeholders como `curl https://{domain}` sin parámetros provistos obtuvieran `AUTHORIZED` y `can_execute=True`, mientras que la ejecución real en `execute_playbook_step` bloqueaba con código 126.
     - **Solución implementada:** Se eliminó la excepción de placeholders no expandidos: cualquier paso activo que no resuelva candidatos verificables contra Scope Guard es marcado estáticamente como `BLOCKED` con `can_execute=False`, logrando paridad absoluta con el ejecutor en tiempo de ejecución.
  3. **Verificación Formal con Mocks:**
     - Se añadió verificación explícita mediante `unittest.mock.patch("subprocess.run")` garantizando que ningún paso bloqueado invoque `subprocess.run()`.
- **Archivos modificados:**
  - `scripts/seclab_playbook.py`: Parser sintáctico contextual en `_extract_literal_targets`, exclusión contextual de argumentos de banderas y subcomandos, soporte para hosts RFC 1123 de una sola etiqueta y bloqueo fail-closed en `validate_playbook_against_scope`.
  - `scripts/verify/test_seclab_playbook.py`: +4 nuevas pruebas unitarias exhaustivas cubriendo hosts de una sola etiqueta, colisiones de argumentos (`test`, `get`, `query`, `true`, `false`), no invocación de subprocesos con mocks, single-labels en alcance y paridad estática fail-closed en placeholders.
  - `dashboard/backend/tests/test_playbooks_api.py`: Nuevas pruebas de integración en API para `/validate` y `/step/run` con pasos activos con `{domain}` sin parámetros.
- **Verificación:**
  - `check-python-units.py`: 348 pruebas unitarias aprobadas (+4 pruebas vs Fase 248).
  - Suite de playbooks: `test_seclab_playbook.py` con 41/41 pruebas aprobadas (+4 pruebas).
  - Pruebas semilla: `test_playbook_api_seeds.py` (6/6), `test_playbook_infra_seeds.py` (6/6) y `test_playbook_step_run.py` (2/2) aprobadas.
  - Pruebas backend API: `dashboard.backend.tests.test_playbooks_api` con 2/2 suites aprobadas (incluyendo endpoints `/validate`, `/run` y `/step/run`).
  - `git diff --check`: Salida limpia, cero advertencias de formato o espacios en blanco sobrantes.
