# Fase 71: Agregador de Contexto para Agentes (`pt-context`), Suite Completa de Prompts y Exportador en `pt-skills`

## 1. Contexto y Objetivos

Para maximizar la autonomía, precisión y rigor metodológico de agentes de inteligencia artificial y operadores humanos en `seclab-sbf`, esta fase consolida el **puente de contexto bidireccional** entre los artefactos del engagement y los modelos de lenguaje:

1. **Agregador de Contexto para Agentes (`pt-context`)**:
   - Módulo determinista en Python stdlib (`scripts/pt-agent-context.py`), expuesto como `/usr/local/bin/pt-agent-context` con permisos `0555` en la imagen del laboratorio.
   - Sintetiza de manera unificada y en tiempo real:
     - **Reglas de Compromiso y Alcance**: Dominios, IPs, CIDRs y endpoints in-scope; exclusiones explícitas out-of-scope; límites operacionales (tasa de peticiones por segundo, concurrencia máxima, prohibiciones de DoS).
     - **Superficie de Ataque y Reconocimiento**: Conteo y muestras de servicios vivos (`live_hosts.txt`), subdominios (`subdomains.txt`), URLs indexadas, archivos JavaScript y patrones detectados por `gf` (`patterns/`).
     - **Matriz Consolidada de Hallazgos (`evidence/*.md`)**: Conteo por severidad (Crítico, Alto, Medio, Bajo, Informativo) y tabla estructurada con ID, Severidad, Activo, CWE y Título.
     - **Trazabilidad de Auditoría**: Líneas y tamaño de `terminal.log`, extrayendo los hitos forenses más recientes (`[AUDIT-MARK]`).
     - **Inyección de Directivas Metodológicas**: Inclusión contextual de directivas de skills (`SKILL.md`) o prompts de agentes según la especialidad solicitada (`--skill <nombre>`).
   - Salida formateada en **Markdown denso** (óptimo para inyección en ventana de contexto de LLMs) o **JSON estructurado** (`--json`), con soporte de exportación a archivo (`--output`) y copia al portapapeles del sistema (`--copy` vía `xclip`/`pbcopy`).

2. **Suite Completa de Prompts de Agentes Especializados (6 Roles)**:
   - Sincronización idéntica y bidireccional entre `skills/prompts/` y `workspace-seed/templates/prompts/`:
     - `recon-agent.prompt.md`: Mapeo pasivo/activo de superficie y descubrimiento de activos.
     - `auth-agent.prompt.md`: Evaluación de control de acceso, matrices multi-rol, IDOR/BFLA y JWT sin alteración no autorizada.
     - `logic-agent.prompt.md`: Transiciones de estado ilícitas, salteo de pasos y condiciones de carrera seguras.
     - `injection-agent.prompt.md`: Detección segura de SSRF (asistida por `pt-callback`), SSTI y fallos estructurales.
     - `triage-agent.prompt.md`: Filtro anti-ruido, descarte de falsos positivos y compuerta Evidence-First.
     - `report-agent.prompt.md`: Compilación técnica y ejecutiva hacia `REPORT.md` con métricas CVSS.

3. **Ergonomía de Shell y Navegación de Prompts (`pt-skills` / `pentest-lab.plugin.zsh`)**:
   - Incorporación de `pt-context` con aliases: `ptcontext`, `agentcontext`, `pt-ctx`, `ctx`.
   - Soporte para subcomandos en `pt-skills`:
     - `pt-skills prompt [nombre]`: Inspección directa o selector interactivo con `fzf` y previsualización de las plantillas de prompts de agentes.
     - `pt-skills view <skill>`: Visualización directa de playbooks metodológicos sin invocar `fzf`.
   - Actualización de la ayuda global `pt-help`.

---

## 2. Matriz de Prompts y Roles de Agente

| Prompt | Rol Operativo | Guardrails Críticos |
|---|---|---|
| `recon-agent.prompt.md` | Reconocimiento Autónomo | Verificación previa de scope con `pt-scope check`, pasivo sobre activo, límites de concurrencia. |
| `auth-agent.prompt.md` | Control de Acceso & Auth | Pruebas multi-rol con cuentas canarias de prueba, cero interacción con datos reales, sin fuerza bruta. |
| `logic-agent.prompt.md` | Lógica de Negocio & Estados | Cero compras o transacciones reales (solo Sandbox), concurrencia controlada, secuencias cronológicas. |
| `injection-agent.prompt.md` | Inyecciones & SSRF | Canaries aritméticos (`{{7*7}}`), receptor local seguro `pt-callback`, prohibidas sentencias destructivas. |
| `triage-agent.prompt.md` | Triaje & Gatekeeper | Evidence-First (sin raw curl no hay hallazgo), descarte de errores HTTP 500 y barreras de WAF como vulnerabilidades. |
| `report-agent.prompt.md` | Redacción de Informes | Solo evidencias validadas en `evidence/*.md`, vectores CVSS v3.1 justificados, mitigación en dos capas. |

---

## 3. Uso y Ejemplos Prácticos

### Sintetizar Contexto de un Engagement
```bash
# Sintetizar engagement actual o activo
pt-context

# Sintetizar engagement específico
pt-context acme-corp

# Inyectar directivas de autorización y control de acceso
pt-context acme-corp auth

# Exportar en formato JSON estructurado
pt-context acme-corp logic --json

# Copiar el contexto directamente al portapapeles
pt-context acme-corp recon --copy
```

### Consultar Plantillas de Prompts de Agentes
```bash
# Ver lista de prompts disponibles
pt-skills prompt

# Inspeccionar el prompt del agente de autenticación
pt-skills prompt auth

# Inspeccionar el prompt del agente de lógica de negocio
pt-skills prompt logic
```

---

## 4. Verificaciones y Calidad

1. **Pruebas Unitarias Python (`scripts/verify/check-python-units.py`)**:
   - `test_agent_context_aggregator`: Valida la recolección determinista de datos de scope, recon, evidencias y bitácora, así como la resolución de skills/prompts y el render en Markdown y JSON.
   - `test_agent_security_skills_framework`: Valida la integridad estructural de las 10 habilidades metodológicas, la presencia y paridad de las 6 plantillas de prompts de agentes en `skills/prompts/` y `workspace-seed/templates/prompts/`, y los helpers de shell.
   - `test_pentest_lab_plugin_helpers_and_aliases`: Valida helpers (`pt-context()`) y aliases (`ptcontext`, `agentcontext`, `pt-ctx`, `ctx`).
   - Total: **60/60 pruebas unitarias en verde**.

2. **Suite de Calidad Completa (`make verify`)**:
   - Gitleaks (0 secretos en código).
   - Hadolint (Dockerfiles validados).
   - ShellCheck, Actionlint y comprobación estructural de Makefile en verde.
   - Verificación de Compose (`make compose-config`).
