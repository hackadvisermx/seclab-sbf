# Fase 206: vista ligera de supervisión y checkpoints de auditoría (/supervision)

Fecha: 2026-10-12 UTC. Rama `phase/206-supervision-view`, base `279e535`. V3-06a parcial.

## Problema y cambio

En entornos de auditoría colaborativa y formación en ciberseguridad, un supervisor o instructor necesita conocer el progreso real del operador sin tener que navegar por múltiples paneles o archivos independientes. Conforme al criterio de aceptación V3-06:
1. No existía un resumen unificado que respondiera en una sola consulta: qué etapa está activa (`scope`, `recon`, `probing`, `triage`, `reporting`), qué decisiones o evidencias faltan y si hay bloqueos del Scope Guard.
2. Faltaban checkpoints pedagógicos formales que evalúen de manera determinista los requisitos de cada etapa antes de avanzar.
3. Se requería evitar la exposición accidental de secretos de otros engagements mientras se inspeccionan las decisiones y relaciones de evidencia.

En esta fase:
1. Módulo evaluador de checkpoints (`scripts/seclab_supervision.py`):
   - `evaluate_supervision_checkpoints(engagement_dir)`: analiza deterministamente el estado de 4 checkpoints clave:
     - `cp_scope`: Definición y autorización de alcance (`allow_passive` o `allow_active` en `target.yaml`).
     - `cp_recon`: Mapeo de superficie y hosts vivos (`recon/live_hosts.txt`, `subdomains.txt`).
     - `cp_evidence`: Documentación estructurada de hallazgos (`evidence/*.md`).
     - `cp_report`: Informe técnico de auditoría y paquete de entregables exportado (`REPORT.md`, `deliverables/`).
   - Cada checkpoint incluye `status` (`PASSED`, `IN_PROGRESS`, `PENDING`, `BLOCKED`, `NOT_STARTED`), `reason` explicativo y `hint` pedagógico.
2. Servicio y API backend (`dashboard/backend/app/services/supervision_service.py` y `engagements.py`):
   - Nuevo servicio `supervision_service.get_supervision_state(eng_id, eng_type)` que agrega la visión integral: etapa actual, estado de scope, conteo de hosts vivos y subdominios, resumen de hallazgos por severidad (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `INFO`), estado de evidencias y entregables.
   - Endpoint `GET /api/v1/engagements/{eng_id}/supervision` para consulta autenticada de supervisión.
3. Pruebas y verificación:
   - Python unit tests: `scripts/verify/test_supervision_checkpoints.py` integrado en `check-python-units.py` (273 tests acumulados).
   - Backend tests: `dashboard/backend/tests/test_supervision_service.py` en Docker validando la respuesta estructurada y endpoint HTTP.

## Verificación y límites

- Verificado localmente en suite Python y Docker backend.
- Proporciona la capa de datos y checkpoints para la supervisión ligera; la integración visual dedicada en el dashboard puede extenderse en fases subsiguientes.
