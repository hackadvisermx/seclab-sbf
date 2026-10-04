---
name: param-discovery
description: Fuzzing y descubrimiento de parámetros HTTP ocultos y rutas de API mediante heurísticas en Rust (x8).
version: 1.0.0
author: hackadvisermx/seclab-sbf
license: MIT
category: fuzzing
tools:
  - x8
  - pt-fuzz-params
  - ffuf
---

# Skill: Parameter & API Route Discovery (`param-discovery`)

## 1. Propósito y Alcance

Esta habilidad guía al agente en la identificación de parámetros GET, POST, cabeceras personalizadas y rutas API no documentadas en endpoints web. Utiliza el motor en Rust `x8` y el helper `pt-fuzz-params`, que evalúan variaciones heurísticas de longitud, palabras reflejadas y códigos HTTP de respuesta.

---

## 2. Precondiciones y Guardrails

1. **Endpoint en Scope**:
   - El endpoint a analizar debe pertenecer a un host listado como autorizado en `/workspace/engagements/<engagement>/scope.txt`.
2. **Control de Concurrencia y Carga**:
   - Ajustar el retardo de peticiones para no saturar APIs frágiles ni disparar defensas automáticas de bloqueo IP:
     - Usar entre 5 y 15 peticiones concurrentes (`-c 10`).
3. **Manejo de Métricas de Ruido**:
   - `x8` detecta páginas dinámicas que varían en cada petición (e.g. timestamps o tokens CSRF). Si la respuesta base es inestable, configurar parámetros de comparación estricta o headers estáticos.

---

## 3. Flujo de Ejecución Paso a Paso

### Paso 1: Preparación del Entorno
```bash
ENGAGEMENT="<nombre_engagement>"
FUZZ_DIR="/workspace/engagements/${ENGAGEMENT}/fuzzing"
mkdir -p "${FUZZ_DIR}"
```

### Paso 2: Selección de Wordlist
El laboratorio incluye colecciones estándar en `/usr/share/seclists/`:
- Parámetros web comunes: `/usr/share/seclists/Discovery/Web-Content/burp-parameter-names.txt`
- Parámetros de API REST: `/usr/share/seclists/Discovery/Web-Content/api/api-endpoints.txt`

### Paso 3: Fuzzing con `pt-fuzz-params` / `x8`

#### Caso A: Parámetros GET en Endpoint Específico
```bash
TARGET_URL="https://target.example.com/api/v1/search"
pt-fuzz-params \
  -u "${TARGET_URL}" \
  -w /usr/share/seclists/Discovery/Web-Content/burp-parameter-names.txt \
  -o "${FUZZ_DIR}/params_search_get.json" \
  --output-format json
```

#### Caso B: Parámetros POST con Cuerpo JSON
```bash
TARGET_URL="https://target.example.com/api/v1/profile"
x8 \
  -u "${TARGET_URL}" \
  -X POST \
  --body '{"user":"test"}' \
  --headers "Content-Type: application/json" \
  -w /usr/share/seclists/Discovery/Web-Content/burp-parameter-names.txt \
  -o "${FUZZ_DIR}/params_profile_post.json" \
  --output-format json
```

### Paso 4: Análisis Heurístico de Resultados

El agente debe examinar el archivo JSON resultante y evaluar:
1. **Parámetros Descubiertos**: Variables que provocaron una respuesta divergente en el servidor.
2. **Reflejo en la Respuesta**: Parámetros cuyos valores son reflejados directamente en el cuerpo HTML/JSON (candidatos prioritarios para XSS o inyección de plantillas).
3. **Códigos de Estado Inusuales**: Cambios de `404` a `200`, o de `403` a `500` cuando un parámetro específico es enviado (candidatos para Bypass de Autenticación, IDOR o Debug parameters).

---

## 4. Registro de Resultados

Si se identifican parámetros anómalos o de depuración (`debug`, `admin`, `test`, `role`, `redirect_to`):
```bash
pt-log mark "Fuzzing completado en ${TARGET_URL}: parámetros sospechosos identificados en ${FUZZ_DIR}/params_*.json"
```

El agente documentará los parámetros encontrados como insumo directo para la habilidad `triage-gatekeeper`.
