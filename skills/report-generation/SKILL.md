---
name: report-generation
description: Generación de reportes de auditoría y bug bounty estructurados con CVSS v3.1/v4.0 y referencias de evidencia.
version: 1.0.0
author: hackadvisermx/seclab-sbf
license: MIT
category: reporting
tools:
  - view_file
  - write_to_file
---

# Skill: Standardized Report Generation (`report-generation`)

## 1. Propósito y Alcance

Esta habilidad consolida las evidencias validadas por la compuerta de triaje (`evidence/*.md`), el registro de auditoría (`terminal.log`) y el alcance definido (`scope.txt`), redactando un reporte técnico y ejecutivo final en `/workspace/engagements/<engagement>/REPORT.md`.

El reporte es compatible con los estándares de entrega para clientes corporativos y plataformas de Bug Bounty (HackerOne, Bugcrowd).

---

## 2. Precondiciones y Guardrails

1. **Evidencias Validadas**:
   - Todo hallazgo incluido DEBE provenir de un archivo de evidencia validado en `evidence/VULN-*.md`.
2. **Puntuación de Severidad Estándar**:
   - Debe calcularse el vector CVSS v3.1 o CVSS v4.0 para cada hallazgo, justificando métricas de vector de ataque (AV), complejidad (AC), privilegios requeridos (PR) e interacción de usuario (UI).
3. **Remediaciones Accionables**:
   - Cada vulnerabilidad debe incluir recomendaciones técnicas específicas de corrección a nivel de código o configuración, no solo consejos genéricos.

---

## 3. Flujo de Ejecución Paso a Paso

### Paso 1: Recolección y Consolidación de Evidencias
El agente debe leer:
1. `/workspace/engagements/<engagement>/scope.txt`
2. Todos los archivos `/workspace/engagements/<engagement>/evidence/VULN-*.md`
3. Las marcas de auditoría en `/workspace/engagements/<engagement>/terminal.log`

### Paso 2: Cálculo de Matriz de Severidad
Agrupar los hallazgos según su impacto y calcular métricas:

| Severidad | Rango CVSS | Hallazgos Identificados |
|---|---|---|
| Crítica | 9.0 - 10.0 | RCE, SQLi sin autenticación, Bypass total de autenticación |
| Alta | 7.0 - 8.9 | IDOR con cambio de privilegios, SSRF ciego en metadata |
| Media | 4.0 - 6.9 | XSS almacenado, divulgación de PII menor |
| Baja | 0.1 - 3.9 | Divulgación de versiones, cabeceras débiles con vector |

### Paso 3: Generación del Archivo `REPORT.md`
Escribir el informe estructurado en `/workspace/engagements/<engagement>/REPORT.md` con la siguiente plantilla:

```markdown
# Reporte Técnico de Seguridad y Auditoría

**Objetivo:** [Nombre del Sistema / Organización]  
**Engagement ID:** [ID de Engagement]  
**Fecha de Emisión:** YYYY-MM-DD  
**Auditor / Tester:** tester (`seclab-sbf`)  
**Metodología:** PTES / OWASP Web Security Testing Guide (WSTG v4.2) / Evidence-First  

---

## 1. Resumen Ejecutivo
[Descripción para directivos y tomadores de decisiones: objetivo analizado, nivel global de exposición, hallazgo más crítico y conclusión general del estado de seguridad.]

---

## 2. Alcance y Trazabilidad

- **Activos Autorizados:** [Detalle de dominios e IPs analizadas según scope.txt]
- **Bitácora de Auditoría:** `terminal.log` (Hash SHA-256 inmutable de la sesión)
- **Ventana Operativa:** [Fechas y horarios de ejecución]

---

## 3. Matriz de Hallazgos y Severidad

| ID | Título de la Vulnerabilidad | Severidad | CVSS v3.1 | CWE / OWASP | Estado |
|---|---|---|---|---|---|
| VULN-01 | [Nombre] | [Crítica/Alta/Media/Baja] | [Puntaje] | [CWE-XXX] | Confirmado |

---

## 4. Detalle Técnico de Vulnerabilidades

### 4.1 [VULN-01]: [Título del Hallazgo]

- **Severidad:** [Crítica] - CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N (Puntaje: 9.1)
- **CWE / OWASP:** CWE-89 / OWASP A03:2021-Injection
- **Endpoint Afectado:** `POST /api/v1/auth/login`

#### A. Causa Raíz
[Explicación concisa del fallo en la validación o manejo de lógica]

#### B. Pasos de Reproducción (PoC)
1. Enviar la siguiente petición HTTP:
\`\`\`http
POST /api/v1/auth/login HTTP/1.1
Host: target.example.com
...
\`\`\`
2. Observar la respuesta del servidor:
\`\`\`http
HTTP/1.1 200 OK
...
\`\`\`

#### C. Demostración de Impacto
[Evidencia del impacto demostrado empíricamente]

#### D. Referencia en Bitácora Forense
- Ver marca temporal en `terminal.log`: `[Timestamp]`

#### E. Recomendaciones de Remediación
- **Inmediata:** Uso de sentencias preparadas (Prepared Statements / Parameterized Queries).
- **Estructural:** Implementación de validación estricta de esquemas de entrada y principio de mínimo privilegio en base de datos.

---

## 5. Conclusión y Próximos Pasos
[Resumen de remediación priorizada y recomendaciones de re-test]
```
