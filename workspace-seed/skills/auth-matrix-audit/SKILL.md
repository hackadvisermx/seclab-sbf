---
name: auth-matrix-audit
description: Auditoría rigurosa de matrices de control de acceso, elevación de privilegios horizontal/vertical (IDOR) y ciclo de vida de sesiones y tokens.
version: 1.0.0
author: hackadvisermx/seclab-sbf
license: MIT
category: auth
tools:
  - curl
  - jq
  - pt-log
  - view_file
---

# Skill: Authentication & Access Control Matrix Audit (`auth-matrix-audit`)

## 1. Propósito y Alcance

Inspirada en la **Fase 01 de mdpsec/bug-bounty-hunting-prompts**, esta habilidad guía al agente en la evaluación metodológica de controles de autenticación, matrices de autorización entre múltiples roles y el ciclo de vida de tokens de sesión.

Su objetivo es detectar de forma reproducible:
- **BOLA / IDOR (Broken Object Level Authorization)**: Acceso o modificación no autorizada de recursos entre usuarios del mismo nivel de privilegio (elevación horizontal).
- **BFLA (Broken Function Level Authorization)**: Ejecución de acciones administrativas por parte de usuarios con privilegios regulares o no autenticados (elevación vertical).
- **Fallas en la Gestión de Sesión**: Falta de revocación tras logout, tokens JWT sin validación de firma o expiraciones infinitas.

---

## 2. Precondiciones y Guardrails (Compuerta de Control de Acceso)

1. **Cuentas de Prueba Autorizadas**:
   - Se debe contar con al menos dos cuentas de prueba creadas explícitamente para la evaluación:
     - **Usuario A (Víctima simulada)**: Propietario de los objetos y recursos de prueba.
     - **Usuario B (Atacante simulado)**: Usuario con privilegios estándar sin acceso legítimo a los datos de A.
     - *(Opcional)* **Usuario Admin**: Para contrastar permisos de funciones restringidas.
   - **PROHIBIDO**: Probar con identificadores de cuentas reales o usuarios de producción.
2. **Alcance y Trazabilidad**:
   - Todo endpoint evaluado debe estar registrado en `/workspace/engagements/<engagement>/scope.txt`.
   - Iniciar registro forense si no está activo: `pt-log start <engagement>`.
3. **Comportamiento Esperado vs Anomalía**:
   - `401 Unauthorized` / `403 Forbidden`: Comportamiento seguro esperado.
   - `200 OK` devolviendo datos privados de Usuario A al solicitar con token de Usuario B: **Hallazgo Crítico/Alto (IDOR confirmado)**.

---

## 3. Flujo de Ejecución Paso a Paso

### Paso 1: Mapeo de la Matriz de Control de Acceso
Construir una tabla de prueba de endpoints clave:

```text
Endpoint                     Método  Usuario A (Owner)  Usuario B (Cross)  Anónimo
/api/v1/orders/{order_id}    GET     200 OK (Legítimo)  ?                  ?
/api/v1/orders/{order_id}    PUT     200 OK (Legítimo)  ?                  ?
/api/v1/admin/users          GET     403 Forbidden      ?                  ?
```

### Paso 2: Prueba de Elevación Horizontal (IDOR / BOLA)
1. Obtener identificador de recurso perteneciente a Usuario A (e.g. `ORDER_ID="ord_1001"`).
2. Ejecutar la petición HTTP utilizando el token de sesión de Usuario B:

```bash
ENGAGEMENT="<nombre_engagement>"
EVIDENCE_DIR="/workspace/engagements/${ENGAGEMENT}/evidence"
mkdir -p "${EVIDENCE_DIR}"

TOKEN_USER_B="<jwt_o_cookie_usuario_b>"
TARGET_URL="https://target.example.com/api/v1/orders/ord_1001"

curl -isk -X GET "${TARGET_URL}" \
  -H "Authorization: Bearer ${TOKEN_USER_B}" \
  -H "Accept: application/json" \
  > "${EVIDENCE_DIR}/test_idor_ord1001.txt"
```

3. **Validación**:
   - Si la respuesta contiene datos confidenciales del Usuario A (nombre, dirección, datos financieros) con código `200 OK`, el IDOR está confirmado.

### Paso 3: Prueba de Elevación Vertical (BFLA)
Intentar invocar rutas o métodos administrativos desde el contexto de Usuario B o usuario anónimo:

```bash
ADMIN_URL="https://target.example.com/api/v1/admin/settings"

# Caso A: Con token de usuario regular
curl -isk -X GET "${ADMIN_URL}" \
  -H "Authorization: Bearer ${TOKEN_USER_B}" \
  > "${EVIDENCE_DIR}/test_bfla_user_b.txt"

# Caso B: Reemplazando método (Method Tampering / Verb Tunneling)
curl -isk -X POST "${ADMIN_URL}" \
  -H "X-HTTP-Method-Override: GET" \
  -H "Authorization: Bearer ${TOKEN_USER_B}" \
  > "${EVIDENCE_DIR}/test_bfla_override.txt"
```

### Paso 4: Auditoría de Tokens de Sesión (JWT / Cookies)
1. **Inspección de Claims**:
   ```bash
   # Decodificar payload de JWT sin verificar firma para revisar claims de rol
   printf '%s' "${TOKEN_USER_B}" | cut -d'.' -f2 | base64 -d 2>/dev/null | jq .
   ```
2. **Prueba de Invalidation Post-Logout**:
   - Usuario B ejecuta logout en la aplicación.
   - Repetir una petición previamente autorizada con el mismo token. Si el servidor responde `200 OK`, la sesión no fue invalidada en servidor (Session Revocation Failure).

---

## 4. Registro y Salida

Si se confirma una vulnerabilidad de control de acceso:
1. Sellar la bitácora con `pt-log`:
   ```bash
   pt-log mark "VULN-AUTH-01: Confirmado IDOR en ${TARGET_URL} - Usuario B puede acceder a registros de Usuario A"
   ```
2. Generar ficha estructurada en `${EVIDENCE_DIR}/VULN-AUTH-01.md`:
   - Identificadores de objetos evaluados.
   - Peticiones y respuestas completas de Usuario A vs Usuario B.
   - Severidad CVSS v3.1 / v4.0 (usualmente Alta: `8.5` - `AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:N`).
   - Remediación técnica (validación de propiedad a nivel de capa de datos con `WHERE user_id = :session_user_id`).
