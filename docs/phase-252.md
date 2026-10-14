# Fase 252 — Remediación Integral de Auditoría (Ronda 9): Control de Alcance sobre Parámetros Interpolados No Canónicos (B3)

## Resumen Ejecutivo

- **ID de Mejora:** Auditoría de Seguridad & Robustecimiento de Salvaguardas — Ronda 9 (Blocker B3).
- **Objetivo:** Resolver de manera rigurosa y puntual la omisión de Scope Guard ante parámetros posicionales no canónicos interpolados en playbooks activos:
  1. **B3 — Validación Fail-Closed de Parámetros Posicionales Interpolados:**
     - En `scripts/seclab_playbook.py`, `is_target_placeholder` condicionaba la incorporación de parámetros únicamente a nombres canónicos (`domain`, `target`, `host`, etc.) o banderas reconocidas (`-x`, `--url`, `-connect`, etc.).
     - Ante comandos como `curl {asset} target.local` con `parameters={"asset": "evil.com"}`, `{asset}` no era catalogado como destino, provocando que solo se evaluara `target.local` contra Scope Guard. Esto autorizaba indebidamente el paso estáticamente y en tiempo de ejecución, invocando `subprocess.run("curl evil.com target.local")` hacia un destino no autorizado.
     - **Solución implementada:**
       - **Ampliación de Placeholders No-Objetivo:** Se agregaron `method` y `methods` a `NON_TARGET_PLACEHOLDERS`.
       - **Detección Contextual de No-Objetivos:** Se implementó en `is_target_placeholder` la discriminación de banderas que esperan valores operacionales (`FLAGS_EXPECTING_NON_TARGET_VALUE`), tales como `-X {verb}`, `-w {wordlist}`, `-o {output}` o cargas útiles en `-d '{"query":"{...}"}'`.
       - **Regla Fail-Closed para Posicionales y Ambiguos:** Cualquier placeholder en un paso activo que no esté demostrablemente excluido de ser un destino es clasificado como candidato a objetivo de red.
       - **Extracción de Destinos Interpolados:**
         - En `extract_step_targets`, todo parámetro interpolado provisto en `parameters` es añadido a `targets` salvo que sea demostrablemente no relacionado con objetivos.
         - Se añade la inspección directa de destinos literales en el comando resultante tras la interpolación (`interpolate_command(cmd_tpl, params)`).
       - **Salvaguarda Fail-Closed en Tiempo de Ejecución:** En `execute_playbook_step`, previo a cualquier invocación a `subprocess.run()`, se re-evalúan todos los literales extraídos del comando interpolado `cmd` contra Scope Guard, bloqueando con código 126 (`BLOCKED`) sin invocar `subprocess.run()` ante cualquier objetivo fuera de alcance.
  2. **Verificación Formal con Mocks:**
     - Pruebas unitarias mediante `unittest.mock.patch("subprocess.run")` certifican que ante parámetros como `curl {asset} target.local` con `asset="evil.com"` o sin parámetro provisto, el paso bloquea con código 126 (`BLOCKED`) y `subprocess.run` nunca es llamado (`mock_run.assert_not_called()`).
     - Pruebas API en `/api/v1/playbooks/validate` para el caso posicional `curl {asset} target.local` fuera de alcance, sin resolver y en alcance.
- **Archivos modificados:**
  - `scripts/seclab_playbook.py`: Refactorización de `is_target_placeholder`, extracción de literales de comandos interpolados en `extract_step_targets`, y salvaguarda fail-closed previa a ejecución en `execute_playbook_step`.
  - `scripts/verify/test_seclab_playbook.py`: +1 nueva prueba unitaria (`test_b3_interpolated_positional_parameter_validates_against_scope`) alcanzando 47 pruebas en la suite.
  - `dashboard/backend/tests/test_playbooks_api.py`: Casos de prueba en `/api/v1/playbooks/validate` para parámetros posicionales no canónicos.
- **Verificación:**
  - `check-python-units.py`: 354 pruebas unitarias aprobadas (+1 prueba vs Fase 251).
  - Suite de playbooks: `test_seclab_playbook.py` con 47/47 pruebas aprobadas (+1 prueba).
  - Pruebas semilla: `test_playbook_api_seeds.py` (6/6), `test_playbook_infra_seeds.py` (6/6) y `test_playbook_step_run.py` (2/2) aprobadas (total 61 pruebas de playbooks aprobadas).
  - Pruebas backend API: `dashboard.backend.tests.test_playbooks_api` con 2/2 suites aprobadas.
  - `git diff --check`: Salida limpia, cero advertencias de formato o espacios en blanco sobrantes.
