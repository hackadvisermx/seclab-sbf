---
title: "Título de la Vulnerabilidad o Hallazgo"
id: "VULN-01"
severity: "High" # Critical | High | Medium | Low | Info
cvss_v31: "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:N"
cvss_score: 5.3
cwe: "CWE-799"
asset: "https://api.example.com/v1/users/1234/profile"
status: "PROVEN" # PROVEN (Confirmado) | CANDIDATE (Prerrequisito pendiente) | DISPROVED (Falsificado/Descartado) | MITIGATED (Corregido)
auditor: "tester"
date: "YYYY-MM-DD"
audit_log: "terminal.log"
---

# [VULN-01] Título de la Vulnerabilidad o Hallazgo

## 1. Resumen y Causa Raíz
Falta de Limitación de Tasa (Rate Limiting): el endpoint acepta un número ilimitado (o excesivamente alto) de peticiones en una ventana de tiempo corta sin aplicar throttling, bloqueo progresivo ni CAPTCHA, lo que habilita ataques automatizados de fuerza bruta, enumeración o abuso de recursos. Ajustar la severidad real según lo que el endpoint expone: una falta de rate limit en login/recuperación de contraseña (credential stuffing, account takeover) es más crítica que en un endpoint de solo lectura sin datos sensibles.

## 2. Pasos Detallados de Reproducción (PoC)
Pasos deterministas y acotados para confirmar la ausencia de limitación, **sin** ejecutar un ataque de fuerza bruta completo ni agotar cuentas reales:

1. Enviar un número reducido pero suficiente de peticiones consecutivas con credenciales/valores distintos, respetando el límite de tasa configurado en `target.yaml` del engagement (`operational_limits.max_requests_per_second`):
   ```bash
   for i in $(seq 1 20); do
     curl -s -o /dev/null -w "intento %{http_code}\n" -X POST https://api.example.com/v1/auth/login \
       -H "Content-Type: application/json" \
       -d "{\"username\": \"test_user\", \"password\": \"intento_$i\"}"
   done
   ```
2. Confirmar que **ninguna** de las respuestas (ni siquiera hacia el final de la serie) incluye un código `429 Too Many Requests`, cabeceras `Retry-After`/`X-RateLimit-*`, ni un bloqueo/CAPTCHA tras el intento N esperado según la política de seguridad declarada por el cliente.

## 2b. Control Negativo (Negative Control)
Petición de control para descartar que el límite exista pero se active con un umbral distinto al probado, o que haya sido un fallo transitorio de red:
```bash
# Repetir la serie una segunda vez, inmediatamente despues, desde la misma IP.
# Si existiera throttling por IP/cuenta, la segunda serie deberia degradarse (429, retraso
# o bloqueo) incluso si la primera no lo mostro. Ausencia de cambio confirma la falta de control.
for i in $(seq 1 20); do
  curl -s -o /dev/null -w "ronda2 intento %{http_code}\n" -X POST https://api.example.com/v1/auth/login \
    -H "Content-Type: application/json" \
    -d "{\"username\": \"test_user\", \"password\": \"intento2_$i\"}"
done
```

## 2c. Verificación Acotada No Destructiva (Bounded Testing Standard)
- **Alcance acotado**: máximo 20-50 peticiones por serie (ajustar al mínimo necesario para observar el patrón; nunca miles). Respeta siempre `operational_limits.max_requests_per_second` del engagement.
- **Sin denegación de servicio**: esto **no** es una prueba de fuerza bruta real ni un intento de tomar la cuenta objetivo; se usa una cuenta de prueba propia o credenciales claramente inválidas, nunca credenciales reales de terceros.
- **Reversión de estado**: no se generan bloqueos permanentes ni se agota ninguna cuenta legítima; si el endpoint SÍ bloquea tras cierto umbral, detener la prueba de inmediato en cuanto se confirma el comportamiento (no continuar "para ver cuánto aguanta").

## 3. Petición y Respuesta Crudas (Raw HTTP Evidence)

### Petición HTTP (intento repetido, idéntica salvo el valor probado):
```http
POST /v1/auth/login HTTP/1.1
Host: api.example.com
Content-Type: application/json
Content-Length: 52

{"username": "test_user", "password": "intento_20"}
```

### Respuesta HTTP (intento 20, igual que el intento 1 — sin señal de throttling):
```http
HTTP/1.1 401 Unauthorized
Content-Type: application/json
Content-Length: 29

{"error": "invalid_credentials"}
```

## 4. Demostración de Impacto en el Negocio
Sin limitación de tasa, un atacante puede automatizar ataques de fuerza bruta o credential stuffing contra cuentas de usuario (usando listas de credenciales filtradas en otras brechas), enumerar usuarios válidos por diferencias de tiempo/respuesta, o abusar de endpoints costosos en cómputo para degradar el servicio (agotamiento de recursos).

## 5. Remediación Sugerida
- Implementar limitación de tasa por IP y por cuenta/identificador (lo que ocurra primero), con backoff progresivo (exponential backoff) tras intentos fallidos consecutivos.
- Agregar CAPTCHA u otro desafío tras un umbral razonable de intentos fallidos (p. ej. 5-10).
- Considerar bloqueo temporal de cuenta tras múltiples fallos, con notificación al usuario legítimo y mecanismo de desbloqueo seguro.
- Responder con `429 Too Many Requests` y cabecera `Retry-After` cuando se exceda el límite, en vez de seguir procesando la petición con normalidad.

## 6. Referencias
- [OWASP Application Security Verification Standard (ASVS) — V2.2 Authenticator Lifecycle / Rate Limiting](https://owasp.org/www-project-application-security-verification-standard/)
- [CWE-799: Improper Control of Interaction Frequency](https://cwe.mitre.org/data/definitions/799.html)
