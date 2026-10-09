# Fase 166: estados de hallazgos coherentes en triaje y cierre

Fecha: 2026-10-09. Rama `phase/166-finding-state-parity`, base inicial `83feed0`, worktree `/Users/castr/tmp/t01-finding-state-parity`. Entrega parcial V3-02h/V3-03g.

## Problema comprobado

En la imagen phase165, una ficha CANDIDATE con REPORT.md y marcadores de disciplinas producía triaje COMPLETED, cero pendientes y cierre permitido; pt-next recomendaba pack_and_close. Una ficha sin estado producía checklist bloqueado, pero pt-next seguía recomendando cerrar y el contexto la mostraba como Confirmado. Reproducción aislada como tester, raíz de solo lectura y sin red en `tmp/phase166/reproduction.log` del checkout principal.

## Cambio

- Checklist, contexto, siguiente paso y fallback de cierre usan el normalizador compartido de `seclab_findings.py`. Estado ausente/vacío se interpreta como CANDIDATE, UNVERIFIED como DRAFT. Candidatos, borradores, bloqueados y estados desconocidos siguen pendientes; PROVEN y sus alias, DISPROVED y MITIGATED resuelven el estado declarado de triaje.
- El lector limita status al frontmatter escalar, admite CRLF, comillas y comentario exterior. Texto del cuerpo no confirma ni degrada la ficha; claves status duplicadas o comillas incompletas quedan como candidato. No interpreta YAML arbitrario ni migra originales.
- El marcador de triaje no completa la disciplina cuando hay fichas pendientes. Fichas resueltas requieren REPORT.md para completar triaje; se preserva el marcador explícito cuando no existen fichas. Las otras disciplinas conservan su heurística.
- El resumen conserva verified/unverified y añade disproved/mitigated. Un descartado o mitigado no se cuenta como confirmado. Contexto Markdown muestra el estado declarado y deja de titular todos los registros como validados.
- pt-next recomienda revisión humana para las fichas pendientes y solo ofrece cierre si el evaluator lo permite. README, plantillas y archivos ocultos no cuentan como fichas en esos consumidores.

## Validación y estado de integración

```sh
make verify
make build-full BUILD_TAG=-phase166
make dashboard-tests LAB_IMAGE=full-phase166 IMAGE_SOURCE=remote
npm --prefix dashboard/frontend test
npm --prefix dashboard/frontend run audit
npm --prefix dashboard/frontend run test:e2e
npm --prefix dashboard/frontend run test:e2e:integration
make smoke-test SCAN_IMAGE=seclab-sbf:full-phase166
make compose-config ENV_FILE=.env.example LAB_IMAGE=full-phase166
go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.12
make scan-image SCAN_IMAGE=seclab-sbf:full-phase166
```

Primera validación funcional: 186 Python, 195 backend, 118 frontend, audit 0, 3 UI y 5 integraciones Chromium. La regresión instalada de smoke verifica estados/aliases, contexto, next y cierre real bloqueado sin alterar target.yaml. La prueba Python también verifica el fallback sin checklist. Navegador/API comprueban candidato legacy pendiente tras recarga y resolución explícita a DISPROVED, sin nuevos jobs ni proveedor IA en ese caso. Capturas pendientes/resueltas inspeccionadas; fixtures/tester temporal eliminados al terminar. La ampliación del caso de sesión reutiliza el login existente para respetar el límite real de cinco logins por minuto.

El primer scan actualizado bloqueó el gate con CVE-2026-78667 y CVE-2026-97031 en Go de herramientas/payloads y el pebble heredado de Ubuntu. No se agregan excepciones. La fase 167 prepara la corrección de supply chain por separado; esta entrega requiere integrar esa base y repetir build/gates de su head final antes de merge. El hash inicial `4a9427656e59a4fa` corresponde a una validación previa a ajustes finales de fixtures; no es una imagen aprobada para desplegar.

## Compatibilidad y límites

No cambia archivos de proyectos ni exige confirmar un candidato para poder resolverlo: puede descartarse o mitigarse explícitamente. El estado PROVEN aquí es una declaración; check/build/export siguen aplicando las compuertas de evidencia/alcance/motivo de fase162. La cobertura sigue siendo heurística y no garantiza pruebas completas ni ausencia de vulnerabilidades. El cierre con --force conserva la omisión explícita existente.

No añade historial de revisión, IDs inmutables, procedencia finding/job, timeline ni privacidad del contexto. No cambia la política existente ante archivos ilegibles o checklist indisponible salvo la normalización del fallback de cierre; esos límites siguen pendientes. Revert restaura recomendaciones/lecturas anteriores sin migración. Laboratorio vivo, imagen full y proyectos del owner intactos.

Merge por PR hacia bootstrap/baseline, revisión del diff, gates locales y CI aprobado del head exacto. Autorización renovada vigente hasta 2026-10-10 14:56:00 UTC; después vuelve aprobación individual.
