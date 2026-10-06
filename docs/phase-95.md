# Fase 95 — Metodología Bug Bounty Hunting: Gates de Evidencia, Modos de Acceso y Ciclo Evidence-First

Integración de las metodologías esenciales de pruebas de penetración y bug bounty hunting (inspiradas en `mdpsec/bug-bounty-hunting-prompts`) adaptadas al marco estricto, determinista y seguro de SecLab-SBF.

## Pilares Metodológicos Implementados

1. **Gate de Validación de Credenciales con Control Negativo (Negative Control Gate)**:
   - Toda alegación de secretos, tokens o credenciales expuestas (`Authorization: Bearer`, API keys, session tokens) debe pasar por un control negativo explícito:
     - Petición con secreto/token: `200 OK` (autorizado).
     - Petición con token manipulado/expirado/ausente: debe responder deterministamente `401 Unauthorized` o `403 Forbidden`.
   - Si la petición sin credenciales o con credencial falsa también devuelve `200 OK` idéntico, el endpoint es público o ignora la autenticación, descartando falsos positivos en exposición de credenciales y reorientando el análisis.
   - Plantilla [`workspace-seed/templates/evidence.md`](file:///Users/castr/tmp/t01/workspace-seed/templates/evidence.md) actualizada con la sección `## 2b. Control Negativo (Negative Control)`.

2. **Enrutamiento Metodológico por Modo de Acceso (RICH / PARTIAL / UNAUTH)**:
   - Clasificación formal del engagement en [`workspace-seed/templates/target.yaml`](file:///Users/castr/tmp/t01/workspace-seed/templates/target.yaml) según las credenciales disponibles:
     - `RICH`: 2+ cuentas de diferentes usuarios/roles. Permite pruebas de control de acceso bidireccional cruzado (BOLA/IDOR) y pruebas verticales completas (BFLA).
     - `PARTIAL`: 1 sola cuenta autenticada. Enfoque en escalamiento de privilegios vertical (BFLA) y pruebas de mutación sobre recursos propios.
     - `UNAUTH`: 0 cuentas (anónimo). Enfoque estricto en vectores pre-autenticación (descubrimiento de endpoints públicos, inyecciones, fuga de metadatos, SSO, registro y bypass de autenticación).
   - Skills y prompts de agentes (`auth-matrix-audit`, `api-security-audit`, `duplicate-scope-guard`, `triage-gatekeeper`) alineados con este enrutamiento.

3. **Estándar de Prueba Acotada No Destructiva (Bounded Non-Destructive Testing)**:
   - Restricción formal de mutaciones sobre recursos ajenos en pruebas de IDOR/BOLA:
     - Probar mutaciones únicamente sobre recursos creados por las identidades propias del auditor.
     - En recursos ajenos, limitar la prueba a lecturas deterministas no destructivas (1 a 3 peticiones máximo).
     - Prohibición de DoS, rate exhaustion destructivo o modificación masiva de datos en producción.
     - Incorporado como sección `## 2c. Verificación Acotada No Destructiva (Bounded Testing Standard)` en la plantilla de evidencia.

4. **Deduplicación por Causa Raíz y Mitigación Compartida (Root-Cause Convergence)**:
   - Prevención de inflación de reportes: múltiples endpoints con el mismo fallo de autorización subyacente (mismo middleware defectuoso o misma tabla/ORM sin filtro de tenant) deben agruparse en una sola ficha de hallazgo con impacto consolidado, en lugar de generar fichas duplicadas por ruta.
   - Integrado en [`skills/duplicate-scope-guard/SKILL.md`](file:///Users/castr/tmp/t01/skills/duplicate-scope-guard/SKILL.md) y [`workspace-seed/skills/duplicate-scope-guard/SKILL.md`](file:///Users/castr/tmp/t01/workspace-seed/skills/duplicate-scope-guard/SKILL.md).

5. **Ciclo Formal de Estados de Hallazgos Evidence-First**:
   - Estados estandarizados:
     - `PROVEN`: Confirmado deterministamente con PoC y Control Negativo superado.
     - `CANDIDATE`: Hipótesis prometedora en fase de verificación acotada.
     - `DISPROVED`: Falso positivo o hipótesis refutada por el control negativo o comportamiento estándar.
     - `MITIGATED`: Vulnerabilidad remediada y verificada.
     - `DRAFT`: Borrador en redacción.
   - Implementado en:
     - **CLI**: `pt-finding new <id> --status <proven|candidate|disproved|mitigated|draft>` y compilador `pt-report-compiler.py` con normalización bidireccional y detección automática de secciones 2b y 2c.
     - **Backend**: `FindingFrontmatter` y `FindingCreate` en `schemas.py`, soporte en `WorkspaceSyncService` (`save_finding`, `list_findings`, `get_finding`) y fallback compatible para fichas legadas sin campo `status`.
     - **Frontend**: Badge de estado táctico adaptativo en `EngagementDetailView.vue` y selector interactivo en el modal de creación y edición de fichas.

## Validación y Métricas

- `npm --prefix dashboard/frontend test`: 12 pruebas pasando exitosamente.
- `npm --prefix dashboard/frontend run build`: Compilación limpia de producción con Vite.
- `npm --prefix dashboard/frontend run audit`: 0 vulnerabilidades.
- `gitleaks dir . --no-banner --config .gitleaks.toml`: 0 leaks encontrados.
- `make verify`: 117 pruebas Python aprobadas (verificación de scope, target.yaml, compilador y linter de evidencia).
- `make dashboard-tests`: 59 pruebas aprobadas (+4 nuevas pruebas en `test_evidence_first_hunting.py` verificando estados, compatibilidad legada y target.yaml).
