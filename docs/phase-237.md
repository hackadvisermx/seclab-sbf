# Fase 237 — Catálogo Extendido de Playbooks para APIs Modernas (GraphQL y OAuth2/JWT)

## Resumen Ejecutivo

- **ID de Mejora:** V3-04g (Catálogo extendido de playbooks deterministas para auditoría de APIs modernas).
- **Objetivo:** Incorporar procedimientos estructurados y repetibles para el análisis de seguridad de arquitecturas basadas en GraphQL e interfaces de autenticación/autorización OAuth2 y tokens JWT, bajo las políticas estrictas de Scope Guard.
- **Archivos creados:**
  - `workspace-seed/playbooks/api_graphql_audit.yaml`: Procedimiento determinista para introspección de esquema, sondeo de sugerencias de campos (field suggestion fuzzing) y comprobación de límites de profundidad de consultas recursivas.
  - `workspace-seed/playbooks/oauth_jwt_audit.yaml`: Procedimiento determinista para descubrimiento de metadatos OpenID Connect/OAuth2 (.well-known), inspección de claves públicas JWKS y análisis de endpoints de emisión de tokens.
  - `scripts/verify/test_playbook_api_seeds.py`: Pruebas unitarias de esquema y validación contra alcance (con y sin PyYAML).
- **Archivos modificados:**
  - `scripts/verify/test_seclab_playbook.py`: Integración de las nuevas plantillas en la suite canónica de verificación de playbooks.

## Detalles de Implementación

1. **Playbook GraphQL (`api_graphql_audit.yaml`):**
   - ID: `pb_api_graphql_audit`
   - Categoría: `api_audit`
   - Paso 1 (`step_01_graphql_introspection`): Consulta `__schema{types{name}}` para verificar si la introspección está activa en producción.
   - Paso 2 (`step_02_field_suggestion_probing`): Extracción de campos y sondeo de filtración de sugerencias (`queryType{fields{name}}`).
   - Paso 3 (`step_03_query_depth_check`): Sondeo básico de profundidad y tipos anidados (`__typename`).

2. **Playbook OAuth2/JWT (`oauth_jwt_audit.yaml`):**
   - ID: `pb_oauth_jwt_audit`
   - Categoría: `api_audit`
   - Paso 1 (`step_01_openid_discovery`): Descubrimiento pasivo/activo en `/.well-known/openid-configuration`.
   - Paso 2 (`step_02_jwks_inspection`): Recuperación e inspección de claves públicas en `/.well-known/jwks.json`.
   - Paso 3 (`step_03_token_endpoint_probe`): Solicitud al endpoint de tokens sin credenciales para auditar respuestas de error y divulgación de información.

3. **Verificación y Pruebas:**
   - 22 pruebas unitarias de playbooks aprobadas (`test_playbook_api_seeds.py` y `test_seclab_playbook.py`).
   - 304 pruebas de la suite local (`make verify`) aprobadas con 0 errores.
   - 189 pruebas frontend Vitest aprobadas, Vite build exitoso.
