---
title: "Título de la Vulnerabilidad o Hallazgo"
id: "VULN-01"
severity: "High" # Critical | High | Medium | Low | Info
cvss_v31: "CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:C/C:L/I:L/A:N"
cvss_score: 6.1
cwe: "CWE-79"
asset: "https://api.example.com/v1/users/1234/profile"
status: "CANDIDATE" # PROVEN (Confirmado) | CANDIDATE (Prerrequisito pendiente) | DISPROVED (Falsificado/Descartado) | MITIGATED (Corregido)
auditor: "tester"
date: "YYYY-MM-DD"
audit_log: "terminal.log"
---

# [VULN-01] Título de la Vulnerabilidad o Hallazgo

## 1. Resumen y Causa Raíz
Cross-Site Scripting (XSS) Reflejado: un parámetro de la petición se refleja en el cuerpo HTML de la respuesta sin codificación contextual (HTML entity encoding), permitiendo la inyección de marcado y JavaScript arbitrario que se ejecuta en el navegador de la víctima en el contexto de origen de la aplicación.

## 2. Pasos Detallados de Reproducción (PoC)
Pasos deterministas y mínimos para reproducir el comportamiento vulnerable:

1. Enviar el payload de prueba (no destructivo, solo confirma ejecución) en el parámetro vulnerable:
   ```bash
   curl -s "https://api.example.com/v1/search?q=%3Cscript%3Ealert(document.domain)%3C%2Fscript%3E"
   ```
2. Confirmar en la respuesta cruda que el payload aparece sin codificar dentro de una etiqueta HTML ejecutable (no como texto escapado `&lt;script&gt;`):
   ```bash
   curl -s "https://api.example.com/v1/search?q=%3Cscript%3Ealert(document.domain)%3C%2Fscript%3E" | grep -o '<script>alert(document.domain)</script>'
   ```
3. Verificar visualmente en navegador (o con un headless browser) que el `alert()` se ejecuta al cargar la URL, confirmando ejecución real y no solo reflejo textual.

## 2b. Control Negativo (Negative Control)
Petición de control para descartar que el framework ya esté codificando el valor en otro contexto (falso positivo por caché, WAF selectivo o sanitización parcial):
```bash
# Variante con comillas/ángulos HTML-encoded manualmente: si el backend normalizara la entrada,
# ambas peticiones deberían comportarse igual. Si solo el payload crudo se refleja sin escapar,
# se confirma la ausencia de codificación de salida, no un artefacto de la petición de prueba.
curl -s "https://api.example.com/v1/search?q=%26lt%3Bscript%26gt%3Balert(1)%26lt%3B%2Fscript%26gt%3B"
# Resultado esperado del control: el texto aparece literal, sin decodificar ni ejecutar.
```

## 2c. Verificación Acotada No Destructiva (Bounded Testing Standard)
- **Alcance acotado**: 1 a 2 peticiones GET de confirmación; `alert(document.domain)` como payload de prueba de concepto no destructivo, sin exfiltración real de datos ni redirección a infraestructura externa.
- **Sin denegación de servicio**: una sola petición de confirmación visual; no se automatizó ni se repitió en bucle.
- **Reversión de estado**: la petición es idempotente (GET), no modifica datos ni sesiones de otros usuarios.

## 3. Petición y Respuesta Crudas (Raw HTTP Evidence)

### Petición HTTP:
```http
GET /v1/search?q=%3Cscript%3Ealert(document.domain)%3C%2Fscript%3E HTTP/1.1
Host: api.example.com
User-Agent: curl/8.5.0
Accept: */*
```

### Respuesta HTTP:
```http
HTTP/1.1 200 OK
Content-Type: text/html; charset=utf-8
Content-Length: 118

<div class="search-results">Resultados para: <script>alert(document.domain)</script></div>
```

## 4. Demostración de Impacto en el Negocio
Un atacante puede construir un enlace malicioso que, al ser abierto por una víctima autenticada, ejecute JavaScript arbitrario en su sesión: robo de cookies de sesión no `HttpOnly`, suplantación de identidad (acciones en nombre de la víctima), captura de credenciales mediante formularios falsos inyectados en la página (phishing in-page), o pivoteo hacia otras vulnerabilidades del lado del cliente.

## 5. Remediación Sugerida
- Aplicar codificación de salida contextual (HTML entity encoding) a todo dato controlado por el usuario antes de insertarlo en el HTML de respuesta; usar el autoescape nativo del framework/motor de plantillas en vez de concatenación manual de strings.
- Implementar una Content-Security-Policy (`script-src`) restrictiva que impida la ejecución de scripts inline no autorizados, como defensa en profundidad.
- Marcar las cookies de sesión como `HttpOnly` y `Secure` para reducir el impacto de un XSS exitoso.
- Validar y, si aplica, limitar la entrada en el servidor (longitud, charset esperado) sin depender únicamente de la validación del lado del cliente.

## 6. Referencias
- [OWASP XSS Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html)
- [CWE-79: Improper Neutralization of Input During Web Page Generation ('Cross-site Scripting')](https://cwe.mitre.org/data/definitions/79.html)
