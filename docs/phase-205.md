# Fase 205: schema y validación estricta de Playbooks deterministas (seclab_playbook)

Fecha: 2026-10-12 UTC. Rama `phase/205-playbook-schema`, base `43b6ab0`. V3-04a parcial.

## Problema y cambio

Los procedimientos de auditoría y pruebas de intrusión tácticas requieren reproducibilidad, precondiciones explícitas y condiciones de parada claras. Conforme al criterio de aceptación V3-04:
1. Las secuencias de pasos de pruebas operaban frecuentemente como comandos ad-hoc en terminal o documentación dispersa en prosa, sin un esquema formal que defina propósito, precondiciones, entradas, parámetros, timeout y criterios de parada.
2. No existía un validador que impidiera la ejecución de playbooks cuyas acciones activas violaran los permisos o límites de autorización definidos en el contrato de alcance (`target.yaml` bajo V3-01).
3. El operador y el backend no contaban con un catálogo estructurado de playbooks deterministas reutilizables ni con compuertas de validación previa al lanzamiento.

En esta fase:
1. Módulo de playbooks (`scripts/seclab_playbook.py`):
   - `validate_playbook_schema(playbook)`: valida de forma estricta el esquema V3-04a (metadatos `id`, `title`, `version`, `category`, `steps`; y por cada paso: `id`, `title`, `objective`, `interaction_type` (`passive`, `active_low`, `active_high`), `required_permissions`, `command_template`, `timeout_seconds`, `expected_outputs`, `success_criteria`, `stop_conditions`).
   - `validate_playbook_against_scope(playbook, target_yaml)`: evalúa de forma determinista cada paso contra las políticas de autorización de `target.yaml`. Si un paso requiere interacción activa (`active_low` / `active_high`) pero `target.yaml` tiene `allow_active: false`, el paso es marcado de inmediato como `BLOCKED` impidiendo el inicio.
2. Catálogo de plantillas semilla (`workspace-seed/playbooks/`):
   - `web_recon.yaml`: playbook determinista de descubrimiento pasivo de subdominios y sondeo HTTP/HTTPS.
   - `port_discovery.yaml`: playbook determinista de escaneo TCP SYN y mapeo de servicios.
3. Backend y API (`dashboard/backend/app/api/endpoints/playbooks.py` y `router.py`):
   - `GET /api/v1/playbooks`: lista playbooks disponibles (semilla del sistema y personalizados del proyecto).
   - `GET /api/v1/playbooks/{playbook_id}`: inspección detallada de la definición del playbook y estado de validación.
   - `POST /api/v1/playbooks/validate`: compuerta para validar sintaxis de playbooks y autorización de alcance para un engagement específico.
4. Pruebas y verificación:
   - Python tests: `scripts/verify/test_seclab_playbook.py` (7 tests integrados en `check-python-units.py`, acumulando 271 tests).
   - Backend tests: `dashboard/backend/tests/test_playbooks_api.py` en runner Docker probando el listado, detalle y validación HTTP.

## Verificación y límites

- Verificado localmente en suite Python y Docker backend.
- V3-04a formaliza el esquema canónico, catálogo y compuertas de autorización de Playbooks; la interfaz de ejecución paso a paso en dashboard y seguimiento progresivo se completa en fases posteriores.
