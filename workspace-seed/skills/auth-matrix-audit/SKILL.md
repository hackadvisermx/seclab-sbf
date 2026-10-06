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

### A. Modos de Acceso según Identidades Disponibles (`target.yaml` / Vault)
Inspirado en la taxonomía de **Fases 01 y 02 de mdpsec**, el auditor debe derivar su carril de ejecución según las identidades disponibles:
- **Modo RICH (2+ identidades activas)**: Ejecución bidireccional cruzada (Usuario A accede a recursos de B, y Usuario B intenta acceder a recursos de A) más contraste con privilegios administrativos.
- **Modo PARTIAL (1 sola identidad)**: Auditoría de escalamiento vertical (privilegios administrativos) y mutaciones sobre el estado propio.
- **Modo UNAUTH (0 identidades / público)**: Enfoque exclusivo en vectores pre-autenticación (rutas expuestas sin token, manipulación de cabeceras, DOM XSS, Cache Deception y bypasses de autenticación).

### B. Estándar de Prueba Acotada No Destructiva (Bounded Non-Destructive Testing)
1. **Objetos Propios Primero**: Demostrar siempre la vulnerabilidad entre cuentas de prueba controladas por el auditor (Usuario A y Usuario B).
2. **Máximo 3 Verificaciones Acotadas**: Si se evalúa si un ID ajeno o predecible es accesible, realizar a lo sumo **1 a 3 peticiones mínimas de lectura** para confirmar la falta de control sin exfiltrar lotes masivos de datos (no bulk dumps).
3. **Reversión Obligatoria**: Si la prueba involucró una mutación (PUT/PATCH), restaurar inmediatamente el estado original o registrarlo en el log de auditoría.
4. **Prohibición de Denegación de Servicio y Bloqueos**: No alterar contraseñas de terceros ni forzar bloqueos de cuenta.

### C. Comportamiento Esperado vs Anomalía
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

3. **Validación y Control Negativo**:
   - **Control Negativo Obligatorio**: Repetir la petición sin token de autorización o con un token manipulado/expirado:
     ```bash
     curl -isk -X GET "${TARGET_URL}" -H "Authorization: Bearer <TOKEN_INVALIDO>"
     ```
     Debe retornar `401 Unauthorized`. Si retorna `200 OK` idéntico, el endpoint no requiere autenticación (es público), lo cual reclasifica el hallazgo a exposición no autenticada en vez de IDOR.
   - Si la petición con token de Usuario B devuelve `200 OK` con datos confidenciales de Usuario A, y la petición con token inválido devuelve `401/403`, el **IDOR está formalmente confirmado**.

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
