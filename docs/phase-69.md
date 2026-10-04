# Fase 69: Gestor de Hallazgos (`pt-finding`), Compilador de Informes (`pt-report`) y Habilidad de API Security (`api-security-audit`)

## 1. Contexto y Objetivos

Para cerrar el ciclo completo de auditoría ofensiva ética —desde el scaffolding del engagement hasta la generación automatizada de informes ejecutivos y técnicos para clientes o programas de bug bounty—, esta fase incorpora:

1. **Gestión Estructurada de Hallazgos (`pt-finding` / `pt-vuln`)**:
   - Plantilla estándar de evidencia en [`workspace-seed/templates/evidence.md`](../workspace-seed/templates/evidence.md) con frontmatter YAML y secciones estandarizadas (Severidad, vector y score CVSS v3.1, identificador CWE, activo evaluado, estado de confirmación, pasos de reproducción, petición/respuesta crudas, impacto en el negocio y remediación sugerida).
   - Scaffolding instantáneo mediante `pt-finding new <slug>` con marcado automático en la bitácora continua de `pt-log` bajo tmux.
   - Linter de calidad Evidence-First mediante `pt-finding check`, que verifica la presencia obligatoria de comandos `curl` reproducibles, remediación y comprueba contra `pt-scope` que ningún hallazgo afecte activos excluidos o fuera de alcance.

2. **Compilador Automático de Informes (`pt-report`)**:
   - Binario determinista en Python ([`scripts/pt-report-compiler.py`](../scripts/pt-report-compiler.py)), instalado en el contenedor como `/usr/local/bin/pt-report-compiler` sin dependencias externas obligatorias.
   - Lee `target.yaml` y unifica todas las fichas en `evidence/*.md` para compilar un `REPORT.md` exhaustivo y profesional:
     - Resumen ejecutivo con postura global de riesgo y desglose por severidad.
     - Tabla del alcance y límites operacionales (reglas de engagement).
     - Matriz consolidada de vulnerabilidades ordenada por severidad (Crítica -> Alta -> Media -> Baja -> Informativa).
     - Secciones técnicas completas con comandos de reproducción y evidencias HTTP crudas.
     - Registro de limpieza post-engagement y trazabilidad forense vinculada a `terminal.log`.
   - Modos en terminal: `pt-report build`, `pt-report view` y `pt-report status`.

3. **Habilidad Metodológica: `api-security-audit` (Fase 06 de mdpsec)**:
   - Nueva Agent Security Skill en [`skills/api-security-audit/SKILL.md`](../skills/api-security-audit/SKILL.md) y reflejada en `workspace-seed/skills/`.
   - Guía sistemática para evaluación de APIs modernas (REST, GraphQL, Webhooks):
     - Detección de Mass Assignment en payloads JSON (`role`, `is_admin`, `verified`).
     - HTTP Verb Tampering y omisión de BFLA vía métodos alternativos o cabeceras `X-HTTP-Method-Override`.
     - Introspección y técnicas de batching en GraphQL para evasión de rate-limiting.
     - Pruebas de replay protection y evasión de validación de firmas HMAC en webhooks.

---

## 2. Componentes e Implementación

### 2.1 Plantilla de Evidencia (`workspace-seed/templates/evidence.md`)
Estructura mínima obligatoria:
- Frontmatter: `title`, `id`, `severity` (Critical, High, Medium, Low, Info), `cvss_v31`, `cvss_score`, `cwe`, `asset`, `status`, `auditor`, `date`, `audit_log`.
- Secciones:
  - `## 1. Resumen y Causa Raíz`
  - `## 2. Pasos Detallados de Reproducción (PoC)` (comandos curl deterministas)
  - `## 3. Petición y Respuesta Crudas (Raw HTTP Evidence)`
  - `## 4. Demostración de Impacto en el Negocio`
  - `## 5. Remediación Sugerida`
  - `## 6. Referencias`

### 2.2 Compilador y Linter (`scripts/pt-report-compiler.py`)
- `list <dir>`: Muestra tabla con formato ANSI de hallazgos ordenados por severidad.
- `check <dir>`: Linter que valida completitud evidence-first e invoca `pt-scope-validator` para rechazar activos fuera de alcance.
- `build <dir> [salida]`: Genera `REPORT.md` integrando `target.yaml` y las fichas de `evidence/*.md`.

### 2.3 Funciones de Shell (`shell/pentest-lab/pentest-lab.plugin.zsh`)
- `pt-finding new <slug> [--title "..."] [--severity ...] [--asset ...]`: Crea la ficha en `evidence/<slug>.md`, reemplaza variables e inserta una marca en `pt-log`.
- `pt-finding list [engagement]`: Muestra hallazgos en terminal.
- `pt-finding check [engagement]`: Ejecuta el linter sobre las evidencias.
- `pt-report build [engagement] [salida]`: Compila el informe.
- `pt-report view [engagement]`: Abre el reporte con `less` conservando formato.
- `pt-report status [engagement]`: Resumen de estado.
- Aliases incorporados: `ptfinding`, `ptvuln`, `finding`, `vuln`, `ptreport`, `report`.

---

## 3. Pruebas y Validación

1. **Pruebas Unitarias Python (`scripts/verify/check-python-units.py`)**:
   - `test_finding_manager_and_report_compiler`: Verifica parsing de `evidence.md`, compilación exitosa de `REPORT.md`, y detección/rechazo de activos marcados como `OUT_OF_SCOPE` en `target.yaml`.
   - `test_agent_security_skills_framework`: Valida las 9 habilidades (incluyendo `api-security-audit`).
   - `test_pentest_lab_plugin_helpers_and_aliases`: Valida helpers (`pt-finding()`, `pt-report()`) y sus aliases.
   - Total: **58/58 pruebas en verde**.

2. **Suite de Calidad (`make verify`)**:
   - Gitleaks (0 secretos).
   - Hadolint (Dockerfiles limpios).
   - ShellCheck, Actionlint y verificación de Compose completados sin fallas.
