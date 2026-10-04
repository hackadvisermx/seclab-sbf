# Fase 66: Navegador de Skills en Terminal (`pt-skills`) y Auditoría de Autenticación/Lógica

## 1. Contexto y Objetivos

Tras el establecimiento del framework de Agent Security Skills en la Fase 65, esta fase amplía las capacidades operativas del laboratorio en dos vertientes fundamentales:

1. **Ergonomía y Accesibilidad en Terminal (`pt-skills`)**:
   - Proveer un helper interactivo en Zsh (`pt-skills`, con aliases `ptskills`, `skills` y `pt-skill`) que permita a cualquier operador, estudiante o subagente explorar, consultar y ejecutar los playbooks de habilidades directamente en su sesión de terminal tmux.
   - Incluye integración con `fzf` para búsqueda difusa interactiva, panel de previsualización en vivo (`preview`) y fallback automático en texto plano para entornos no interactivos o sin `fzf`.

2. **Habilidad: Auditoría de Autenticación y Matriz de Acceso (`auth-matrix-audit`)**:
   - Inspirada en la **Fase 01 de [mdpsec/bug-bounty-hunting-prompts](https://github.com/mdpsec/bug-bounty-hunting-prompts)**.
   - Metodología rigurosa para contrastar matrices de roles (Usuario A vs Usuario B vs Admin vs Anónimo).
   - Detección reproducible de elevación horizontal (IDOR / BOLA) y vertical (BFLA), inspección de claims en JWT y verificación de invalidación de sesión post-logout.

3. **Habilidad: Auditoría de Lógica de Negocio y Transición de Estados (`business-logic-audit`)**:
   - Inspirada en la **Fase 03 de [mdpsec/bug-bounty-hunting-prompts](https://github.com/mdpsec/bug-bounty-hunting-prompts)**.
   - Detección de violaciones en máquinas de estado (Step Skipping / Forced Browsing en checkouts o wizards multi-paso).
   - Manipulación de parámetros numéricos críticos (cantidades negativas, precios alterados, redondeos indebidos).
   - Detección controlada de condiciones de carrera (Race Conditions / TOCTOU en canje de cupones o retiros de saldo) limitando ráfagas a un máximo seguro de concurrencia.

---

## 2. Decisiones de Arquitectura y Seguridad

### 2.1 Resolución Dinámica de Skills (`pt-skills-dir`)
El helper localiza el catálogo de habilidades evaluando en orden:
1. Variable explícita de entorno `SECLAB_SKILLS_DIR`.
2. Montaje del workspace persistente `/workspace/skills`.
3. Directorio relativo `./workspace/skills` o `skills/` en la raíz del repositorio.
4. Ruta del sistema `/usr/local/share/seclab/skills`.

### 2.2 Guardrails No Negociables en Lógica de Negocio
- **Cuentas y Datos Simulados**: Todo análisis de IDOR o autorización exige cuentas de prueba (`Usuario A` y `Usuario B`) generadas para la auditoría; prohibido interactuar con cuentas ajenas o de producción.
- **Transacciones en Sandbox**: Toda prueba que involucre compras o transacciones financieras debe restringirse a pasarelas en modo sandbox/testing.
- **Límite de Ráfaga Anti-DoS**: En pruebas de condiciones de carrera, las ráfagas paralelas se limitan estrictamente a un máximo de 10 peticiones concurrentes para impedir caídas de servicio o saturación de bases de datos.
- **Trazabilidad Inmutable**: Toda evidencia validada se sella con `pt-log mark` hacia `terminal.log`.

---

## 3. Catálogo Actualizado de Skills (6 Habilidades)

| Skill | Categoría | Herramientas | Enfoque Metodológico |
|---|---|---|---|
| `recon-profiling` | `recon` | `assetfinder`, `findomain`, `httprobe`, `gau`, `gf` | Mapeo de superficie pasivo/activo en scope. |
| `param-discovery` | `fuzzing` | `x8`, `pt-fuzz-params`, `ffuf` | Descubrimiento heurístico de parámetros en Rust. |
| `triage-gatekeeper` | `triage` | `pt-log`, `curl`, `view_file` | Compuerta en 5 puntos anti-alucinaciones y anti-ruido WAF. |
| `report-generation` | `reporting` | `view_file`, `write_to_file` | Reporte final con CVSS v3.1/v4.0 y enlaces forenses. |
| `auth-matrix-audit` | `auth` | `curl`, `jq`, `pt-log` | Matriz de autorización, IDOR, BFLA, JWT y sesión. |
| `business-logic-audit` | `logic` | `curl`, `jq`, `pt-log` | Saltos de estado, parámetros de negocio y condiciones de carrera. |

---

## 4. Verificaciones y Calidad

- **Pruebas Unitarias Python (`scripts/verify/check-python-units.py`)**:
  - `test_agent_security_skills_framework`: Verifica la estructura, frontmatter YAML, categorías obligatorias (`recon`, `fuzzing`, `triage`, `reporting`, `auth`, `logic`) y paridad exacta entre `skills/` y `workspace-seed/skills/`.
  - `test_pentest_lab_plugin_helpers_and_aliases`: Verifica la existencia de `pt-skills-dir()`, `pt-skills()`, los aliases `ptskills`, `skills`, `pt-skill` y su presencia en `pt-help` (56/56 pruebas en verde).
- **Verificación Completa (`make verify`)**: Gitleaks sin filtraciones, Hadolint limpio, ShellCheck limpio, validación estructural de Makefile y Compose sin desviaciones.
