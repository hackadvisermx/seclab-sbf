---
name: api-security-audit
description: Auditoría metodológica de APIs modernas (REST, GraphQL, Webhooks), Mass Assignment, BFLA y evasión de firmas HMAC.
version: 1.0.0
author: hackadvisermx/seclab-sbf
license: MIT
category: api
tools:
  - curl
  - jq
  - pt-log
  - view_file
---

# Skill: Modern API & Webhook Security Audit (`api-security-audit`)

## 1. Propósito y Alcance

Inspirada en la **Fase 06 de mdpsec/bug-bounty-hunting-prompts** y alineada con el estándar **OWASP API Security Top 10**, esta habilidad guía al agente en la evaluación rigurosa de APIs REST, endpoints GraphQL y mecanismos de integración basados en webhooks.

Su objetivo es detectar fallos estructurales de seguridad en capas de servicios:
- **Mass Assignment (Asignación Masiva)**: Modificación no autorizada de propiedades internas o administrativas del modelo de datos (`is_admin`, `role`, `balance`, `verified`) mediante payloads JSON no filtrados.
- **HTTP Verb Tampering & BFLA**: Evasión de controles de acceso manipulando métodos HTTP (`HEAD`, `PUT`, `PATCH`, `DELETE`) o cabeceras de sobreescritura (`X-HTTP-Method-Override`).
- **Inseguridad en GraphQL**: Introspección expuesta en producción, consultas circulares, ataques de amplificación por batching y falta de control de profundidad.
- **Fallas en Webhooks y Firmas Criptográficas**: Evasión de validación de firma HMAC (secretos nulos, comparación en tiempo no constante, ataques de repetición o ausencia de validación de timestamp).

---

## 2. Precondiciones y Guardrails

1. **Cumplimiento del Alcance (`target.yaml`)**:
   - Todo endpoint de API evaluado debe estar comprendido en `in_scope.endpoints` o `in_scope.domains` de `target.yaml`.
   - Validar previamente con: `pt-scope check <api_endpoint>`.
2. **Límites Operacionales Estrictos**:
   - Respetar la tasa de peticiones definida en `operational_limits.max_requests_per_second` (por defecto <= 1 req/s).
   - No ejecutar pruebas destructivas de denegación de servicio por agotamiento de recursos o recursión infinita en GraphQL.
3. **Registro Forense Continuo**:
   - Asegurar que la sesión esté auditada en tmux mediante `pt-log start <engagement>`.
   - Cada comportamiento anómalo o vector explotable debe marcarse con `pt-log mark "API-AUDIT: <detalle>"`.

---

## 3. Flujo de Ejecución Paso a Paso

### Paso 1: Reconocimiento y Mapeo de Definiciones de API
1. Identificar rutas de especificación OpenAPI, Swagger o colecciones Postman:
   ```bash
   for path in /swagger.json /api-docs /v1/swagger.json /openapi.json /v2/api-docs; do
     curl -s -o /dev/null -w "%{http_code} %{url_effective}\n" "https://api.example.com$path"
   done
   ```
2. Inspeccionar esquemas de datos buscando atributos mutables y roles disponibles.

### Paso 2: Evaluación de Mass Assignment
1. Identificar peticiones legítimas de actualización de perfil o registro:
   ```bash
   curl -i -s -X PUT https://api.example.com/v1/users/me \
     -H "Authorization: Bearer <TOKEN>" \
     -H "Content-Type: application/json" \
     -d '{"name": "Alice Tester"}'
   ```
2. Inyectar claves candidatas de privilegios elevados observando si el backend las persiste o las refleja en la respuesta:
   ```bash
   curl -i -s -X PUT https://api.example.com/v1/users/me \
     -H "Authorization: Bearer <TOKEN>" \
     -H "Content-Type: application/json" \
     -d '{
       "name": "Alice Tester",
       "is_admin": true,
       "role": "administrator",
       "verified": true,
       "account_type": "enterprise"
     }'
   ```
3. Verificar persistencia realizando un `GET /v1/users/me`.

### Paso 3: HTTP Verb Tampering y Sobreescritura de Métodos
1. Si un endpoint retorna `403 Forbidden` en peticiones estándar:
   ```bash
   curl -i -s -X GET https://api.example.com/v1/admin/audit-logs \
     -H "Authorization: Bearer <TOKEN_REGULAR>"
   ```
2. Evaluar métodos alternativos y cabeceras de sobreescritura:
   ```bash
   # Prueba con verbos alternativos
   curl -i -s -X POST https://api.example.com/v1/admin/audit-logs -H "X-HTTP-Method-Override: GET"
   curl -i -s -X HEAD https://api.example.com/v1/admin/audit-logs
   curl -i -s -X OPTIONS https://api.example.com/v1/admin/audit-logs
   ```

### Paso 4: Auditoría de Endpoints GraphQL
1. Consultar habilitación de introspección:
   ```bash
   curl -i -s -X POST https://api.example.com/graphql \
     -H "Content-Type: application/json" \
     -d '{"query": "{ __schema { types { name } } }"}'
   ```
2. Si la introspección devuelve el esquema completo, extraer mutaciones administrativas sensibles (`deleteUser`, `updateUserRole`, `exportData`).
3. Evaluar técnicas de Batching para saltarse controles de rate-limiting:
   ```bash
   curl -i -s -X POST https://api.example.com/graphql \
     -H "Content-Type: application/json" \
     -d '[{"query": "query { me { email } }"}, {"query": "query { me { email } }"}]'
   ```

### Paso 5: Seguridad en Webhooks y Firmas Criptográficas
1. Si la aplicación consume o despacha webhooks protegidos por firma (e.g. `X-Webhook-Signature`):
   - Probar envío sin cabecera de firma (validar si el servidor asume petición no firmada como válida).
   - Probar con cabecera vacía o firma nula.
   - Enviar payload original re-enviado tras ventana de expiración (validar Replay Protection).

### Paso 6: Validación de Credenciales Expuestas (Credential-Validation Gate)
Inspirado en la disciplina de **Fase 07 / 2b de mdpsec**: si se descubren claves API, tokens JWT o secretos expuestos en JavaScript, respuestas o endpoints:
1. **Prueba de Liveness Mínima**: Realizar una única petición ligera para confirmar que el secreto es válido en el proveedor (e.g. `GET /v1/me` o endpoint de introspección).
2. **Control Negativo Obligatorio**: Repetir la misma petición utilizando un secreto falsificado o revocado (`Bearer token_falso_invalido`).
   - Si la petición con secreto falso devuelve `200 OK` idéntico, el endpoint **NO valida** la autenticación: descartar el hallazgo de secreto expuesto.
   - Solo si el control negativo devuelve `401 Unauthorized` o `403 Forbidden` se confirma que la clave es activa y requerida.
3. **Escalamiento Acotado de Autoridad**: Probar únicamente el alcance de permisos propios del token (listar capacidades o consultar metadatos). **PROHIBIDO** acceder, modificar o enumerar datos masivos de otros tenants.

---

## 4. Validación de Hallazgos y Criterio Evidence-First

Para catalogar una anomalía como hallazgo confirmado:
1. **Evidencia Completa**: Capturar request y response crudos incluyendo cabeceras y códigos HTTP.
2. **Control Negativo Demostrado**: Documentar el resultado de la petición de control con valor inválido para certificar la existencia de la barrera de seguridad vulnerada.
3. **Demostración de Persistencia**: No basta con que la API retorne `200 OK`; se debe comprobar que el cambio surtió efecto en la lógica de negocio (e.g., el usuario ahora puede realizar acciones de administrador).
4. **Descartar Comportamientos Cosméticos**: Si la API acepta el JSON pero ignora silenciosamente los campos no autorizados sin modificar el estado real, registrarlo como seguro y no levantar falsa alarma.

---

## 5. Salida Estructurada y Registro Forense

1. Marcar el hallazgo en el registro de auditoría:
   ```bash
   pt-log mark "VULN-API-01: Mass assignment confirmado en /v1/users/me (role modificado a administrator)"
   ```
2. Generar la ficha de evidencia con el gestor de hallazgos:
   ```bash
   pt-finding new api-mass-assignment --title "Mass Assignment en /v1/users/me permite elevación a administrador" --severity high
   ```
3. Completar los pasos de reproducción, el control negativo y la respuesta HTTP cruda en `evidence/api-mass-assignment.md`.
