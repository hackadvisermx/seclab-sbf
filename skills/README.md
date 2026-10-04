# seclab-sbf Agent Security Skills

Este directorio contiene las especificaciones y flujos de trabajo de **Agent Skills** para `seclab-sbf`. Siguen la especificación abierta de Agent Skills (`SKILL.md` con frontmatter YAML) para permitir que agentes de inteligencia artificial (Antigravity, Claude Code, subagentes o scripts) ejecuten auditorías éticas de seguridad y actividades de bug bounty con disciplina, reproducibilidad y rigor metodológico.

---

## 1. Principios No Negociables del Agente

1. **Uso Ético y Autorizado**: Ninguna acción debe ejecutarse fuera de los objetivos expresamente autorizados en `scope.txt` o `engagement.yaml` (`docs/uso-autorizado.md`).
2. **Evidence-First**: La evidencia empírica manda. Ninguna vulnerabilidad se reporta sin pares de petición/respuesta reproducibles, códigos de estado verificados y demostración de impacto en la lógica de negocio.
3. **No-Destructive**: Prohibido ejecutar acciones que provoquen denegación de servicio (DoS), saturación de memoria, o alteración no autorizada de datos de producción.
4. **Trazabilidad Continua**: Cada hallazgo relevante debe ser sellado con una marca en el log de auditoría mediante `pt-log mark "VULN-<ID>: <descripción>"`.

---

## 2. Catálogo de Skills

| Skill | Directorio | Categoría | Descripción |
|---|---|---|---|
| **Reconocimiento & Perfilado** | [`recon-profiling`](./recon-profiling/SKILL.md) | `recon` | Mapeo pasivo/activo de dominios, subdominios, rutas web y filtrado de patrones de riesgo con `gf`. |
| **Descubrimiento de Parámetros** | [`param-discovery`](./param-discovery/SKILL.md) | `fuzzing` | Fuzzing rápido de parámetros HTTP ocultos y rutas REST/JSON mediante `x8` y `pt-fuzz-params`. |
| **Compuerta de Triaje** | [`triage-gatekeeper`](./triage-gatekeeper/SKILL.md) | `triage` | Filtro anti-alucinaciones y anti-ruido (falsos positivos, WAFs) con validación estricta de evidencia. |
| **Generación de Reportes** | [`report-generation`](./report-generation/SKILL.md) | `reporting` | Redacción de informes técnicos y ejecutivos con métricas CVSS v3.1 / v4.0 y enlaces a logs de auditoría. |
| **Matriz de Control de Acceso** | [`auth-matrix-audit`](./auth-matrix-audit/SKILL.md) | `auth` | Auditoría de autorización horizontal/vertical (IDOR), validación de JWT y ciclo de vida de sesiones. |
| **Lógica de Negocio y Estados** | [`business-logic-audit`](./business-logic-audit/SKILL.md) | `logic` | Detección de salto de estados, manipulación de precios/cantidades y condiciones de carrera (Race Conditions). |
| **Client-Side & SPAs** | [`client-side-spa-audit`](./client-side-spa-audit/SKILL.md) | `client` | Auditoría de aplicaciones React/SPA, endpoints en JavaScript, configuraciones CORS y postMessage. |
| **Seguridad de APIs & Webhooks** | [`api-security-audit`](./api-security-audit/SKILL.md) | `api` | Auditoría de APIs REST y GraphQL, Mass Assignment, Verb Tampering y validación de firmas HMAC. |
| **Inyecciones de Servidor & SSRF** | [`ssrf-injection-audit`](./ssrf-injection-audit/SKILL.md) | `injection` | Evaluación controlada de SSRF reflejado/ciego, SSTI con canaries aritméticos y fallos estructurales. |
| **Guardia de Scope y Duplicados** | [`duplicate-scope-guard`](./duplicate-scope-guard/SKILL.md) | `guard` | Filtro pre-reporte para evitar penalizaciones por duplicados o hallazgos fuera de política de alcance. |

---

## 3. Estructura de Salida en el Workspace

Cada engagement evaluado bajo estas skills organiza sus artefactos en `/workspace/engagements/<id>/`:

```text
/workspace/engagements/<id>/
├── scope.txt               # Límites, activos y autorizaciones
├── terminal.log            # Bitácora continua capturada por pt-log
├── recon/                  # Salidas de subdominios, puertos y URLs
│   ├── subdomains.txt
│   ├── live_hosts.txt
│   ├── urls_all.txt
│   └── patterns/           # Salidas filtradas por gf (xss, sqli, ssrf, etc.)
├── fuzzing/                # Resultados de parámetros con x8
│   └── params_<target>.json
├── evidence/               # Fichas de vulnerabilidades validadas
│   ├── VULN-01.md
│   └── VULN-02.md
└── REPORT.md               # Informe final generado
```

---

## 4. Suite de Prompts para Agentes Especializados

Ubicados en `skills/prompts/` (y sincronizados en `/workspace/templates/prompts/`), proporcionan los system prompts operativos y guardrails anti-alucinación para modelos de lenguaje autónomos:

| Prompt | Archivo | Rol Operativo |
|---|---|---|
| **Reconocimiento Autónomo** | [`recon-agent.prompt.md`](./prompts/recon-agent.prompt.md) | Mapeo pasivo/activo de superficie y descubrimiento de activos. |
| **Control de Acceso & Auth** | [`auth-agent.prompt.md`](./prompts/auth-agent.prompt.md) | Pruebas de IDOR/BFLA, matrices multi-rol y tokens JWT sin alteración no autorizada. |
| **Lógica de Negocio & Estados** | [`logic-agent.prompt.md`](./prompts/logic-agent.prompt.md) | Transiciones ilícitas, salteo de pasos y condiciones de carrera seguras. |
| **Inyecciones & SSRF** | [`injection-agent.prompt.md`](./prompts/injection-agent.prompt.md) | Detección segura de SSRF (vía `pt-callback`), SSTI y fallos estructurales. |
| **Triaje & Compuerta de Calidad** | [`triage-agent.prompt.md`](./prompts/triage-agent.prompt.md) | Filtro anti-ruido, descarte de falsos positivos y verificación Evidence-First. |
| **Redacción de Reportes** | [`report-agent.prompt.md`](./prompts/report-agent.prompt.md) | Compilación técnica y ejecutiva hacia `REPORT.md` con métricas CVSS. |

---

## 5. Agregador de Contexto para Agentes (`pt-context`)

El comando `pt-context` (`/usr/local/bin/pt-agent-context`) sintetiza en tiempo real:
1. Alcance, exclusiones y límites operacionales de `target.yaml` / `scope.txt`.
2. Resumen de reconocimiento (hosts vivos, URLs, subdominios, patrones de `gf`).
3. Matriz consolidada de hallazgos en `evidence/*.md`.
4. Bitácora de terminal y marcas forenses de `terminal.log`.
5. Playbook metodológico o system prompt del agente asignado (`--skill <nombre>`).

```bash
# Sintetizar contexto del engagement activo
pt-context

# Sintetizar engagement específico inyectando directivas de autorización
pt-context acme-corp auth

# Exportar en formato JSON o copiar al portapapeles
pt-context acme-corp logic --json
pt-context --copy
```

