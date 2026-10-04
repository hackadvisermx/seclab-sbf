---
name: recon-profiling
description: Reconocimiento pasivo y activo acotado al scope autorizado para mapear la superficie de ataque web sin alucinaciones.
version: 1.0.0
author: hackadvisermx/seclab-sbf
license: MIT
category: recon
tools:
  - pt-recon
  - assetfinder
  - findomain
  - httprobe
  - httpx
  - gau
  - gf
  - qsreplace
---

# Skill: Recon & Target Profiling (`recon-profiling`)

## 1. Propósito y Alcance

Esta habilidad guía al agente en la fase inicial de reconocimiento de un objetivo autorizado. Su propósito es enumerar activos vivos, descubrir rutas históricas/pasivas y filtrar parámetros susceptibles a vulnerabilidades web, organizando la salida de forma estructurada en `/workspace/engagements/<engagement>/recon/`.

---

## 2. Precondiciones y Guardrails

1. **Lectura Obligatoria de Alcance**:
   - Antes de ejecutar cualquier herramienta, el agente DEBE leer `/workspace/engagements/<engagement>/scope.txt`.
   - Si el dominio o IP objetivo NO está listado en `scope.txt`, la ejecución se DETIENE de inmediato informando al operador.
2. **Prohibición de DoS**:
   - Ajustar siempre la tasa de peticiones concurrentes (`httpx -rate-limit 30`, `gau --threads 5`).
3. **Inicio de Logging**:
   - Verificar si `pt-log status` está activo. Si no, iniciar `pt-log start <engagement>`.

---

## 3. Flujo de Ejecución Paso a Paso

### Paso 1: Creación de Estructura de Reconocimiento
```bash
ENGAGEMENT="<nombre_engagement>"
RECON_DIR="/workspace/engagements/${ENGAGEMENT}/recon"
mkdir -p "${RECON_DIR}/patterns"
```

### Paso 2: Descubrimiento Pasivo de Subdominios
Para un dominio principal autorizado `$TARGET_DOMAIN`:
```bash
# Enumeración pasiva sin enviar tráfico directo al objetivo
assetfinder --subs-only "${TARGET_DOMAIN}" | sort -u > "${RECON_DIR}/subs_assetfinder.txt"
findomain --target "${TARGET_DOMAIN}" --quiet -u "${RECON_DIR}/subs_findomain.txt"

# Consolidar subdominios únicos
cat "${RECON_DIR}"/subs_*.txt | sort -u | grep -E "\.${TARGET_DOMAIN}$" > "${RECON_DIR}/subdomains.txt"
```

### Paso 3: Identificación de Servicios Web Vivos (Probing)
```bash
# Filtrar qué subdominios responden activamente por HTTP/HTTPS
cat "${RECON_DIR}/subdomains.txt" | httprobe -c 20 -t 3000 | sort -u > "${RECON_DIR}/live_hosts.txt"

# Opcional: extracción detallada de tecnologías y códigos HTTP con httpx
httpx -l "${RECON_DIR}/live_hosts.txt" -status-code -title -tech-detect -silent > "${RECON_DIR}/httpx_summary.txt"
```

### Paso 4: Cosecha Pasiva de URLs Históricas
```bash
# Extraer URLs pasivas indexadas en Wayback, AlienVault OTX, URLScan
cat "${RECON_DIR}/live_hosts.txt" | gau --subs --threads 5 | sort -u > "${RECON_DIR}/urls_all.txt"

# Normalizar URLs con parámetros (descartar duplicados estáticos)
cat "${RECON_DIR}/urls_all.txt" | grep '=' | qsreplace -a > "${RECON_DIR}/urls_with_params.txt"
```

### Paso 5: Filtrado de Patrones de Riesgo con `gf`
Clasificar las URLs obtenidas según categorías de patrones vulnerables:
```bash
for pattern in xss sqli ssrf idor redirect lfi rce; do
  gf "$pattern" "${RECON_DIR}/urls_all.txt" | sort -u > "${RECON_DIR}/patterns/${pattern}.txt"
done
```

---

## 4. Registro y Salida

Al concluir el reconocimiento, el agente debe generar un resumen estructurado en `${RECON_DIR}/summary.json`:

```json
{
  "engagement": "<nombre_engagement>",
  "target_domain": "<dominio>",
  "timestamp": "ISO-8601",
  "subdomains_found": 0,
  "live_hosts": 0,
  "urls_with_params": 0,
  "potential_vectors": {
    "xss": 0,
    "ssrf": 0,
    "idor": 0,
    "sqli": 0
  }
}
```

Y registrar una marca en la bitácora:
```bash
pt-log mark "Reconocimiento completado para ${TARGET_DOMAIN}: $(wc -l < ${RECON_DIR}/live_hosts.txt) hosts activos identificados."
```
