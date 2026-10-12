# Fase 207: Motor de ejecución y runner determinista de Playbooks (seclab_playbook)

Fecha: 2026-10-12 UTC. Rama `phase/207-playbook-runner`, base `683feb6`. V3-04b parcial.

## Problema y cambio

Una vez establecido el esquema de Playbooks deterministas en la Fase 205 (V3-04a), el sistema requería un motor de ejecución capaz de simular (dry-run) y ejecutar secuencialmente los pasos de un playbook respetando las restricciones de alcance:
1. No existía un mecanismo para interpolar parámetros de ejecución (`{target}`, `{port}`) con sanitización estricta contra inyección de comandos en shell.
2. Faltaba un runner de simulación (`dry-run`) que demuestre de antemano el comando que se lanzaría, las salidas esperadas y las restricciones de autorización sin emitir tráfico de red.
3. Se requería una compuerta que detenga la secuencia de pasos determinista si un paso es bloqueado por el contrato de alcance (`target.yaml`), si falla la ejecución o si se cumple una condición de parada.

En esta fase:
1. Motor y runner de Playbooks (`scripts/seclab_playbook.py`):
   - `interpolate_command(template, params)`: interpola parámetros en plantillas con rechazo explícito de metacaracteres peligrosos (`;`, `&`, `|`, `` ` ``, `$`, saltos de línea).
   - `execute_playbook_step(step, context, dry_run=True)`: simula o ejecuta un paso individual, comprobando autorización previa (`allow_passive` / `allow_active`), capturando salida hasta 128KB y evaluando condición de parada.
   - `run_playbook(playbook_data, target_yaml_path, context, dry_run=True, max_steps=None)`: ejecuta la secuencia completa o hasta el límite de pasos especificado, bloqueando el avance ante fallos o pasos no autorizados.
2. Endpoint en API backend (`dashboard/backend/app/api/endpoints/playbooks.py`):
   - `POST /api/v1/playbooks/{playbook_id}/run`: ejecuta o simula un playbook determinista para el engagement especificado, retornando el desglose de resultados por paso, estado general (`SIMULATED`, `COMPLETED`, `STOPPED`, `BLOCKED`) y comandos generados.
3. Pruebas y verificación:
   - 6 pruebas unitarias nuevas en `scripts/verify/test_seclab_playbook.py` (280 tests en `check-python-units.py`).
   - Pruebas API en `dashboard/backend/tests/test_playbooks_api.py` verificando `POST /api/v1/playbooks/{playbook_id}/run`.

## Verificación y límites

- 280 pruebas Python en host (`python3 scripts/verify/check-python-units.py`) pasando sin errores.
- Pruebas backend verificadas.
- V3-04b parcial: añade el runner y simulación dry-run determinista; la interfaz gráfica interactiva se completará en fases subsiguientes.
