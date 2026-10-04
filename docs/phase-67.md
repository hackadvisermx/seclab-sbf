# Fase 67: Auditoría Client-Side/SPA, Filtro de Duplicados y Plantillas de Prompts

## 1. Contexto y Objetivos

Para completar la integración de las capacidades metodológicas derivadas de **[mdpsec/bug-bounty-hunting-prompts](https://github.com/mdpsec/bug-bounty-hunting-prompts)** y el estándar abierto de **[Awesome-AI-Security-Skills](https://github.com/EvanThomasLuke/Awesome-AI-Security-Skills)**, esta fase incorpora:

1. **Habilidad Metodológica: `client-side-spa-audit` (Fase 04 de mdpsec)**:
   - Análisis de seguridad sobre aplicaciones de página única (SPAs en React, Vue, Angular, Next.js).
   - Extracción de rutas de API no documentadas en bundles JavaScript a partir de los artefactos cosechados por `pt-recon` (`recon/js_files.txt`).
   - Auditoría de configuraciones erróneas de CORS (reflejo de orígenes arbitrarios o `null` con `Access-Control-Allow-Credentials: true`).
   - Detección de receptores inseguros de `window.postMessage` sin verificación de `event.origin` y trazabilidad de fuentes y sumideros de DOM XSS.

2. **Habilidad Metodológica: `duplicate-scope-guard` (Fases 08 y 10 de mdpsec)**:
   - Compuerta de auto-verificación y filtro de calidad previo a la redacción del reporte ("Self-Duplicate Check" & "Out-of-Scope Enforcement").
   - Lista explícita de exclusiones habituales (Self-XSS sin impacto, ausencia de cabeceras de seguridad sin vector, banners de servidor, falta de rate limiting trivial, logout CSRF).
   - Verificación de duplicados en divulgaciones públicas de programas de Bug Bounty (HackerOne Hacktivity / Bugcrowd).

3. **Paquete de Plantillas de Prompts de Sistema para Agentes (`templates/prompts/`)**:
   - `recon-agent.prompt.md`: Directivas de sistema para orquestar agentes autónomos de reconocimiento y mapeo de superficie sin violar el alcance.
   - `triage-agent.prompt.md`: Directivas estrictas anti-alucinaciones y anti-ruido con enfoque *Evidence-First*.
   - `report-agent.prompt.md`: Directivas para redacción de informes con cálculo de vector CVSS v3.1 / v4.0 y separación de audiencias (ejecutiva vs técnica).

---

## 2. Catálogo Consolidado de Agent Security Skills (8 Habilidades)

Con esta fase, el catálogo cubre integralmente las 10 etapas del ciclo de auditoría ofensiva ética y bug bounty:

| # | Habilidad | Categoría | Herramientas | Propósito Metodológico |
|---|---|---|---|---|
| 1 | `recon-profiling` | `recon` | `assetfinder`, `findomain`, `httprobe`, `gau`, `gf` | Mapeo de superficie de ataque y cosecha de URLs pasivas/activas. |
| 2 | `param-discovery` | `fuzzing` | `x8`, `pt-fuzz-params`, `ffuf` | Descubrimiento heurístico de parámetros ocultos y rutas REST. |
| 3 | `triage-gatekeeper` | `triage` | `pt-log`, `curl`, `view_file` | Compuerta de validación en 5 puntos (Evidence-First) y sellado forense. |
| 4 | `report-generation` | `reporting` | `view_file`, `write_to_file` | Generación de informes profesionales con CVSS v3.1/v4.0. |
| 5 | `auth-matrix-audit` | `auth` | `curl`, `jq`, `pt-log` | Matriz de control de acceso, elevación horizontal/vertical (IDOR/BFLA), JWT. |
| 6 | `business-logic-audit` | `logic` | `curl`, `jq`, `pt-log` | Violación de estados (Step Skipping), manipulación de precios y carreras (TOCTOU). |
| 7 | `client-side-spa-audit` | `client` | `curl`, `jq`, `pt-log` | Análisis de bundles JS, orígenes CORS con credenciales y `postMessage`. |
| 8 | `duplicate-scope-guard` | `guard` | `view_file`, `curl`, `pt-log` | Filtro pre-reporte contra duplicados, no-issues y exclusiones de alcance. |

---

## 3. Verificaciones y Calidad

- **Pruebas Unitarias Python (`scripts/verify/check-python-units.py`)**:
  - `test_agent_security_skills_framework`: Valida la integridad estructural de las 8 habilidades en `skills/`, su sincronización en `workspace-seed/skills/`, y la correspondencia idéntica de las 3 plantillas de prompts de agentes en `workspace-seed/templates/prompts/` y `skills/prompts/`.
  - `test_pentest_lab_plugin_helpers_and_aliases`: Valida el helper `pt-skills` y sus aliases (56/56 pruebas en verde).
- **Verificación Completa (`make verify`)**: 100% en verde (Gitleaks, Hadolint, ShellCheck, Compose y Makefile checks).
