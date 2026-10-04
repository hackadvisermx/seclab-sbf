# Fase 70: Inyecciones de Servidor & SSRF (`ssrf-injection-audit`), Prompt de Inyección y Receptor de Callbacks (`pt-callback`)

## 1. Contexto y Objetivos

Para completar el **decálogo de habilidades metodológicas de seguridad** en `seclab-sbf` y cerrar integralmente el catálogo derivado de **[mdpsec/bug-bounty-hunting-prompts](https://github.com/mdpsec/bug-bounty-hunting-prompts)** (Fase 07: Server-Side Injections & SSRF) y el estándar abierto de **[Awesome-AI-Security-Skills](https://github.com/EvanThomasLuke/Awesome-AI-Security-Skills)**, esta fase incorpora:

1. **Habilidad Metodológica: `ssrf-injection-audit` (Categoría: `injection`)**:
   - Evaluación exhaustiva de vulnerabilidades donde entradas no confiables provocan interacciones o ejecuciones en el backend:
     - **Server-Side Request Forgery (SSRF) Reflejado**: Interacción interna donde el backend devuelve la respuesta o encabezados hacia el cliente.
     - **SSRF Ciego (Blind/Out-of-Band)**: Peticiones salientes asíncronas hacia servicios externos o internos que requieren un receptor controlado.
     - **Server-Side Template Injection (SSTI)**: Detección precisa y no destructiva de motores de plantillas (Jinja2, Twig, Freemarker, Thymeleaf, ERB) mediante canaries aritméticos (`{{7*7}}` -> `49`).
     - **Inyecciones Estructurales Básicas**: Validación preliminar de concatenaciones SQL o subprocesos sin alteración de datos de producción.
   - Guardrails estrictos: prohibición explícita de sentencias destructivas (`DROP`, `DELETE`, `UPDATE`), denegación de servicio por demoras (`sleep(100)`), y protección contra exfiltración no autorizada de endpoints de metadata de nubes públicas (`169.254.169.254`).

2. **Plantilla de Sistema para Agentes: `injection-agent.prompt.md`**:
   - Directivas de sistema especializadas en `workspace-seed/templates/prompts/` y `skills/prompts/`.
   - Guía al agente en la ejecución con enfoque *Safe-Validation*: comprobación obligatoria de alcance (`pt-scope check`), uso exclusivo de canaries aritméticos y receptores controlados locales.

3. **Receptor Ergonómico de Callbacks Out-of-Band (`pt-callback`)**:
   - Helper interactivo en Zsh (`pt-callback` con aliases `ptcallback` y `callback`).
   - Servidor HTTP ligero y determinista en Python stdlib que registra peticiones entrantes (timestamp, IP/puerto de origen, método HTTP, ruta, cabeceras completas y cuerpo).
   - Comandos:
     - `pt-callback start [puerto]`: Lanza el receptor en segundo plano (por defecto en el puerto 8888) y sella una marca en `pt-log`.
     - `pt-callback show [n]`: Muestra las últimas peticiones capturadas.
     - `pt-callback tail`: Sigue las peticiones en vivo.
     - `pt-callback status`: Muestra estado y métricas de recepción.
     - `pt-callback stop`: Detiene el servidor y limpia procesos efímeros.

---

## 2. Catálogo Consolidado de Agent Security Skills (10 Habilidades)

Con esta incorporación, el catálogo cubre integralmente las 10 etapas del ciclo ofensivo ético y bug bounty:

| # | Habilidad | Categoría | Herramientas | Propósito Metodológico |
|---|---|---|---|---|
| 1 | `recon-profiling` | `recon` | `assetfinder`, `findomain`, `httprobe`, `gau`, `gf` | Mapeo pasivo/activo de dominios, subdominios y patrones de riesgo. |
| 2 | `param-discovery` | `fuzzing` | `x8`, `pt-fuzz-params`, `ffuf` | Fuzzing rápido de parámetros ocultos y rutas REST. |
| 3 | `auth-matrix-audit` | `auth` | `curl`, `jq`, `pt-log` | Matrices de autorización, IDOR horizontal/vertical y JWT. |
| 4 | `client-side-spa-audit` | `client` | `curl`, `jq`, `pt-log` | Análisis de bundles JS, CORS con credenciales y postMessage. |
| 5 | `business-logic-audit` | `logic` | `curl`, `jq`, `pt-log` | Salto de estados, manipulación de montos y condiciones de carrera. |
| 6 | `api-security-audit` | `api` | `curl`, `jq`, `pt-log` | APIs REST/GraphQL, Mass Assignment, Verb Tampering y firmas HMAC. |
| 7 | `ssrf-injection-audit` | `injection` | `curl`, `pt-callback`, `pt-serv-web`, `pt-log` | Evaluación controlada de SSRF reflejado/ciego y SSTI con canaries. |
| 8 | `triage-gatekeeper` | `triage` | `pt-log`, `curl`, `view_file` | Compuerta de triaje en 5 puntos (Evidence-First) y sellado forense. |
| 9 | `duplicate-scope-guard` | `guard` | `view_file`, `curl`, `pt-log` | Filtro pre-reporte contra duplicados, no-issues y exclusiones. |
| 10 | `report-generation` | `reporting` | `pt-finding`, `pt-report`, `view_file` | Generación y compilación de informes con métricas CVSS v3.1/v4.0. |

---

## 3. Verificaciones y Calidad

1. **Pruebas Unitarias Python (`scripts/verify/check-python-units.py`)**:
   - `test_agent_security_skills_framework`: Verifica la integridad estructural de las 10 habilidades en `skills/`, su sincronización idéntica en `workspace-seed/skills/`, y las 4 plantillas de prompts de agentes.
   - `test_ssrf_injection_audit_and_callback_helper`: Valida la skill `ssrf-injection-audit`, su prompt y el helper `pt-callback`.
   - `test_pentest_lab_plugin_helpers_and_aliases`: Valida helpers (`pt-callback()`) y aliases (`ptcallback`, `callback`).
   - Total: **59/59 pruebas en verde**.

2. **Suite de Calidad (`make verify`)**:
   - Gitleaks (0 secretos).
   - Hadolint (Dockerfiles verificados).
   - ShellCheck y Actionlint en verde.
   - Validación de configuración de Compose (`make compose-config`).
