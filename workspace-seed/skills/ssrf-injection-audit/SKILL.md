---
name: ssrf-injection-audit
description: Metodología rigurosa para evaluación de inyecciones del lado del servidor (SSRF reflejado/ciego, SSTI, SQLi) bajo enfoque no destructivo.
version: 1.0.0
author: hackadvisermx/seclab-sbf
license: MIT
category: injection
tools:
  - curl
  - pt-callback
  - pt-serv-web
  - pt-log
  - view_file
---

# Skill: Server-Side Injections & SSRF Audit (`ssrf-injection-audit`)

## 1. Propósito y Alcance

Inspirada en la **Fase 07 de mdpsec/bug-bounty-hunting-prompts** y alineada con los estándares **OWASP Top 10** (A03:2021 Injection y A10:2021 Server-Side Request Forgery), esta habilidad establece el marco metodológico para evaluar vulnerabilidades donde entradas no confiables provocan comportamientos inseguros en la capa de backend:

- **Server-Side Request Forgery (SSRF)**:
  - **SSRF Reflejado**: El servidor backend ejecuta una petición HTTP interna y refleja el cuerpo o cabeceras de la respuesta al cliente.
  - **SSRF Ciego (Blind/Out-of-Band)**: El backend realiza la petición pero no devuelve el contenido, requiriendo verificación mediante callbacks externos controlados (`pt-callback`).
- **Server-Side Template Injection (SSTI)**:
  - Inyección de expresiones evaluadas por motores de plantillas (Jinja2, Twig, Freemarker, Thymeleaf, ERB, Smarty).
- **Inyecciones Estructurales Básicas (SQLi / Command Injection)**:
  - Validación preliminar y controlada de concatenaciones inseguras en consultas o subprocesos sin alteración destructiva.

---

## 2. Precondiciones y Guardrails (Políticas de No-Destrucción)

1. **Principio de Mínimo Impacto (No-Destructive Testing)**:
   - **PROHIBIDO**: Sentencias SQL de alteración o borrado (`DROP`, `DELETE`, `UPDATE`, `INSERT`, `TRUNCATE`).
   - **PROHIBIDO**: Cargas de denegación de servicio (delays excesivos tipo `pg_sleep(100)`, llamadas recursivas o fork-bombs).
   - **PROHIBIDO**: Probar exfiltración de credenciales reales desde endpoints de metadata cloud (`169.254.169.254`) a menos que el contrato de engagement lo autorice expresamente por escrito.
2. **Validación Mediante Canaries Aritméticos**:
   - Para SSTI, validar primero evaluando expresiones matemáticas neutras:
     - `{{7*7}}` -> `49` (Jinja2/Twig)
     - `${7*7}` -> `49` (Freemarker/Thymeleaf/Spring Expression Language)
     - `<%= 7*7 %>` -> `49` (ERB)
3. **Control Estricto de Alcance (`pt-scope`)**:
   - Todo endpoint evaluado debe validarse previamente con: `pt-scope check <url_o_host>`.
   - Iniciar registro continuo en tmux: `pt-log start <engagement>`.

---

## 3. Flujo de Ejecución Paso a Paso

### Paso 1: Mapeo de Parámetros Susceptibles a SSRF
Identificar funcionalidades del backend que requieran consultar URLs externas o generar recursos remotos:
- Exportadores / convertidores de HTML a PDF (`url`, `target_url`, `pdf_url`).
- Carga de imágenes por URL externa (avatares, logos: `image_url`, `avatar_src`, `icon`).
- Webhooks y notificaciones salientes (`webhook_url`, `callback`, `dest`).
- Importación de feeds (RSS, Atom, XML: `feed_url`, `xml_url`).
- Proxies o gateways internos (`proxy_to`, `forward_addr`, `api_host`).

### Paso 2: Evaluación de SSRF Reflejado
1. Probar resoluciones locales o servicios controlados en el entorno de pruebas:
   ```bash
   # Probar direccionamiento hacia loopback con esquemas alternativos
   curl -i -s -X POST https://api.example.com/v1/fetch-avatar \
     -H "Content-Type: application/json" \
     -d '{"url": "http://127.0.0.1:8080/health"}'
   ```
2. Evaluar técnicas comunes de evasión de listas negras si `127.0.0.1` o `localhost` están bloqueados:
   - Representación decimal o hexadecimal de IP: `http://2130706433/` o `http://0x7f000001/`
   - Redirecciones abiertas controladas (`http://redirector.lab/?url=http://127.0.0.1:8080/`)
   - Notación IPv6: `http://[::1]:8080/`

### Paso 3: Evaluación de SSRF Ciego (OOB) con `pt-callback`
Cuando el backend no refleja la respuesta pero procesa la solicitud asíncronamente:
1. Iniciar el receptor de callbacks seguro en SecLab:
   ```bash
   pt-callback start 8888
   ```
2. Enviar la URL del receptor (o la IP VPN asignada al laboratorio):
   ```bash
   VPN_IP="$(pt-vpn-ip)"
   curl -i -s -X POST https://api.example.com/v1/webhooks/test \
     -H "Content-Type: application/json" \
     -d "{\"callback_url\": \"http://${VPN_IP}:8888/ssrf-test-01\"}"
   ```
3. Verificar si el servidor objetivo contactó al receptor:
   ```bash
   pt-callback show
   ```
4. Si se recibe una petición `GET /ssrf-test-01` proveniente de la IP del backend, el SSRF ciego está confirmado.

### Paso 4: Detección Sistemática de SSTI
1. Identificar parámetros reflejados en respuestas HTML o correos electrónicos (e.g. `name`, `username`, `template`, `message`).
2. Enviar cadena de prueba aritmética básica:
   ```bash
   curl -i -s "https://target.example.com/render?name=Test%7B%7B7*7%7D%7D"
   ```
3. Analizar la respuesta:
   - Si la salida contiene `Test49`: **SSTI Confirmado**.
   - Si la salida contiene `Test{{7*7}}`: Entrada no evaluada o sanitizada correctamente.
   - Si ocurre error `500 Internal Server Error`: Posible intento de evaluación con error sintáctico; inspeccionar stack trace.

### Paso 5: Validación Controlada de Inyecciones SQL
1. Comprobar alteraciones en la lógica booleana sin afectar registros:
   ```bash
   # Peticion de prueba 1 (Verdadero)
   curl -s "https://api.example.com/v1/items?search=widget' AND '1'='1" | wc -c
   # Peticion de prueba 2 (Falso)
   curl -s "https://api.example.com/v1/items?search=widget' AND '1'='2" | wc -c
   ```
2. Si el contenido o conteo de bytes difiere sustancialmente entre ambas condiciones, validar mediante parámetros parametrizados seguros y registrar la vulnerabilidad.

---

## 4. Validación de Hallazgos y Criterio Evidence-First

1. **Prueba de Origen**: En SSRF, documentar fehacientemente que la conexión saliente provino del servidor backend (verificando la IP de origen registrada en `pt-callback show` o `terminal.log`).
2. **Determinismo**: La inyección debe ser reproducible con comandos `curl` idénticos.
3. **Sin Daño Colateral**: En ningún caso se deben realizar volcados masivos no autorizados de bases de datos de producción; la prueba de concepto debe limitarse a la versión del motor de base de datos (`SELECT @@version` o `sqlite_version()`).

---

## 5. Salida Estructurada y Registro Forense

1. Sellar la marca en el log de auditoría:
   ```bash
   pt-log mark "VULN-SSRF-01: SSRF ciego confirmado en /v1/webhooks/test (callback capturado en pt-callback)"
   ```
2. Crear la ficha de evidencia estandarizada:
   ```bash
   pt-finding new ssrf-webhook --title "SSRF Ciego en Endpoint de Webhook permite escaneo interno" --severity high
   ```
3. Incorporar los registros crudos de la petición del backend en `evidence/ssrf-webhook.md`.
4. Compilar el reporte actualizado con `pt-report build`.
