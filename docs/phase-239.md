# Fase 239 — Detección de Deriva DNS y Re-validación Dinámica en Scope Guard

## Resumen Ejecutivo

- **ID de Mejora:** V3-01i (Detección de deriva DNS y re-validación de alcance antes de despacho activo).
- **Objetivo:** Prevenir tráfico accidental hacia infraestructura fuera de contrato debido a fluctuaciones o cambios en registros DNS (DNS drift). Implementar resolución dinámica y re-verificación contra el contrato de alcance (`target.yaml`), persistiendo la caché de resoluciones en `evidence/.dns_records.json`.
- **Archivos creados:**
  - `scripts/verify/test_seclab_dns_drift.py`: Pruebas unitarias de resolución, detección de drift, violaciones de alcance y caché histórico.
  - `dashboard/frontend/tests/dns-drift.test.js`: Pruebas de integración frontend en Vitest para la tarjeta de deriva DNS en la pestaña de Alcance.
- **Archivos modificados:**
  - `scripts/seclab_scope.py`: Implementación de `check_dns_drift` y `evaluate_engagement_dns_drift`.
  - `dashboard/backend/app/services/workspace_sync.py`: Método `get_dns_drift`.
  - `dashboard/backend/app/api/endpoints/scope.py`: Endpoint `GET /api/v1/scope/{eng_id}/dns-drift`.
  - `dashboard/frontend/src/api.js`: Función `api.getDnsDrift`.
  - `dashboard/frontend/src/views/EngagementDetailView.vue`: Tarjeta interactiva `scope-dns-drift-card`, botón `check-dns-drift-btn`, badge reactivo `dns-drift-status-badge` e indicador detallado por dominio `domain-drift-row`.

## Detalles de Implementación

1. **Motor de Detección de Deriva DNS (`scripts/seclab_scope.py`):**
   - Función `check_dns_drift`: Resuelve el dominio (vía `socket.getaddrinfo` o callable simulado `mock_resolver`), compara contra el conjunto de `known_ips`, detecta direcciones agregadas y retiradas, y evalúa cada IP contra las reglas de `check_scope`.
   - Estados canónicos:
     - `IN_SCOPE_STABLE`: Todas las IPs resueltas se encuentran en `in_scope` y coinciden con las IPs conocidas.
     - `DRIFT_WITHIN_SCOPE`: La resolución cambió respecto al historial, pero todas las nuevas IPs están dentro del alcance (`in_scope.ips` o `in_scope.cidrs`).
     - `OUT_OF_SCOPE_VIOLATION`: Una o más IPs resueltas no están autorizadas o pertenecen a `out_of_scope`.
     - `UNRESOLVED`: Error al resolver el dominio (NXDOMAIN, timeout o fallo de red).
   - Función `evaluate_engagement_dns_drift`: Itera sobre todos los dominios de `target.yaml`, lee/actualiza la caché `evidence/.dns_records.json` y resume el estado global (`OK`, `WARNING`, `VIOLATION`).

2. **Capa API Backend (`scope.py` y `workspace_sync.py`):**
   - `GET /api/v1/scope/{eng_id}/dns-drift`: Expone el reporte de deriva DNS en tiempo real para el proyecto especificado.

3. **Interfaz de Usuario Táctica (`EngagementDetailView.vue`):**
   - Tarjeta `scope-dns-drift-card` en la pestaña Alcance con botón de análisis manual `check-dns-drift-btn` e insignias codificadas por color.
   - Listado reactivo de dominios con detalle de IPs resueltas y modificaciones (`+IP`, `-IP`).

4. **Verificación y Pruebas:**
   - 5 pruebas unitarias Python en `scripts/verify/test_seclab_dns_drift.py`.
   - 190 pruebas frontend en Vitest aprobadas, Vite build exitoso.
   - 304 pruebas de `make verify` aprobadas sin errores ni fugas.
