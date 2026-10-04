---
name: client-side-spa-audit
description: Auditoría de seguridad en aplicaciones modernas de una sola página (SPAs), extracción de endpoints JS, CORS y postMessage.
version: 1.0.0
author: hackadvisermx/seclab-sbf
license: MIT
category: client
tools:
  - curl
  - jq
  - pt-log
  - view_file
---

# Skill: Client-Side & Modern Web / SPA Audit (`client-side-spa-audit`)

## 1. Propósito y Alcance

Inspirada en la **Fase 04 de mdpsec/bug-bounty-hunting-prompts**, esta habilidad guía al agente en el análisis de seguridad sobre aplicaciones web modernas basadas en frameworks cliente (React, Vue, Angular, Next.js, Svelte).

Su objetivo es detectar de forma reproducible:
- **Exposición de Rutas y Secretos en Bundles JS**: Identificación de endpoints de API no documentados, credenciales duras o configuraciones internas expuestas en archivos `.js` o source maps (`.map`).
- **Manejadores Inseguros de `postMessage`**: Receptores de mensajes entre ventanas sin validación estricta de origen (`event.origin`), permitiendo robo de tokens o DOM XSS.
- **Configuraciones Erróneas de CORS**: Servidores que reflejan orígenes arbitrarios (`Origin: https://attacker.com`) combinados con `Access-Control-Allow-Credentials: true`, permitiendo la exfiltración de datos autenticados.
- **DOM XSS**: Flujos directos entre fuentes controlables por el usuario (*sources*: `location.hash`, `location.search`, `document.referrer`) y sumideros de ejecución (*sinks*: `innerHTML`, `document.write`, `eval`).

---

## 2. Precondiciones y Guardrails (Compuerta Client-Side)

1. **Scripts en Scope**:
   - Solo deben auditarse archivos JavaScript provenientes de hosts autorizados en `/workspace/engagements/<engagement>/scope.txt`.
2. **Distinción entre Claves Públicas y Secretos Críticos**:
   - Claves de cliente como Firebase API keys, Google Maps keys o Stripe Publishable Keys (`pk_test_...` o `pk_live_...`) están diseñadas por arquitectura para residir en el navegador. **NO** deben reportarse como vulnerabilidad salvo que se demuestre un impacto real (e.g. base de datos Firebase con reglas `read/write: true` sin autenticación).
3. **Prueba de Concepto Mínima**:
   - Todo hallazgo de CORS o `postMessage` debe validarse mediante una PoC en HTML simple servida localmente con `pt-serv-web` antes de ser declarado como vulnerable.

---

## 3. Flujo de Ejecución Paso a Paso

### Paso 1: Localización y Análisis de Archivos JavaScript
Utilizar los archivos generados en la fase de reconocimiento (`recon/js_files.txt`):

```bash
ENGAGEMENT="<nombre_engagement>"
JS_DIR="/workspace/engagements/${ENGAGEMENT}/recon/js"
mkdir -p "${JS_DIR}"

# Descargar bundles JS relevantes para analisis offline
head -n 20 "/workspace/engagements/${ENGAGEMENT}/recon/js_files.txt" | while read -r url; do
  curl -s -L "$url" -o "${JS_DIR}/$(basename "${url%%\?*}")"
done
```

### Paso 2: Extracción de Rutas de API y Endpoints Ocultos
Buscar cadenas que coincidan con rutas REST o GraphQL:
```bash
grep -Ero "['\"](/api/v[0-9]/[a-zA-Z0-9_\/-]+)['\"]" "${JS_DIR}" | sort -u > "${JS_DIR}/extracted_api_routes.txt"
```

### Paso 3: Auditoría de Cabeceras CORS
Verificar si el servidor refleja orígenes no confiables permitiendo credenciales:

```bash
TARGET_API="https://target.example.com/api/v1/user/profile"
EVIDENCE_DIR="/workspace/engagements/${ENGAGEMENT}/evidence"
mkdir -p "${EVIDENCE_DIR}"

# Caso 1: Origen arbitrario de atacante
curl -isk -H "Origin: https://evil-attacker.com" \
     -H "Cookie: session=<token_de_prueba>" \
     "${TARGET_API}" > "${EVIDENCE_DIR}/cors_evil_test.txt"

# Caso 2: Origen null (sandboxed iframes / data URIs)
curl -isk -H "Origin: null" \
     -H "Cookie: session=<token_de_prueba>" \
     "${TARGET_API}" > "${EVIDENCE_DIR}/cors_null_test.txt"
```

**Criterio de Validación de Vulnerabilidad CORS**:
- El servidor responde con:
  `Access-Control-Allow-Origin: https://evil-attacker.com` (o `null`) **Y**
  `Access-Control-Allow-Credentials: true`
- Si no incluye `Access-Control-Allow-Credentials: true`, un origen reflejado sobre un endpoint público NO tiene impacto en confidencialidad de datos autenticados.

### Paso 4: Detección de Manejadores de `postMessage` Inseguros
Buscar en los scripts patrones vulnerables donde se procesan mensajes sin comprobar `event.origin`:

```bash
grep -n -E "window\.addEventListener\(['\"]message['\"]" "${JS_DIR}"/*
```

Verificar si la función receptora:
1. Carece de la comprobación: `if (event.origin !== "https://target.example.com") return;`
2. Pasa `event.data` a un sumidero inseguro (`element.innerHTML = event.data` o `eval(event.data)`).

---

## 4. Registro y Salida

Si se confirma una debilidad client-side con impacto comprobado:
1. Sellar la bitácora con `pt-log`:
   ```bash
   pt-log mark "VULN-CLIENT-01: Confirmada mala configuración CORS con credenciales en ${TARGET_API}"
   ```
2. Generar ficha estructurada en `${EVIDENCE_DIR}/VULN-CLIENT-01.md`:
   - Cabeceras completas de petición y respuesta HTTP.
   - Código de la PoC en HTML (`cors_poc.html`).
   - Severidad CVSS v3.1 / v4.0 (ej. Media/Alta: `CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:U/C:H/I:N/A:N` - 6.5).
   - Remediación técnica: Implementar lista blanca estricta de orígenes permitidos y evitar el reflejo dinámico del header `Origin`.
