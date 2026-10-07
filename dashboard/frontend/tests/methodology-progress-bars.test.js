import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { test } from 'node:test'

// Fase 125 / backlog A19: la pestaña Metodología solo mostraba un
// porcentaje y una lista plana de 8 áreas con una insignia binaria
// (COMPLETED en verde, todo lo demás igual de gris, sin distinguir
// IN_PROGRESS de PENDING). Se añade una barra de progreso visual por
// disciplina y una franja resumen de 8 segmentos (estilo OWASP WSTG
// Tracker) que distinguen completo/parcial/pendiente de un vistazo.

async function readSource() {
  return readFile(new URL('../src/views/EngagementDetailView.vue', import.meta.url), 'utf8')
}

test('loadChecklist normaliza matrix/coverage_score (forma real de pt-audit-checklist -j), no solo areas/coverage_pct', async () => {
  // Bug real preexistente (no introducido en esta fase): `pt-audit-checklist.py -j`
  // siempre devuelve `matrix`/`coverage_score` (scripts/pt-audit-checklist.py
  // evaluate()); `areas`/`coverage_pct` solo existen en el fallback de error de
  // runner_service.get_audit_checklist. La plantilla siempre leyó `areas`/
  // `coverage_pct`, así que una corrida real nunca se reflejaba: la pestaña
  // quedaba en "0% Cobertura" y la lista vacía pese a tener datos reales.
  const source = await readSource()
  const fnBody = source.slice(source.indexOf('async function loadChecklist'), source.indexOf('async function loadNextStepPrompt'))
  assert.match(fnBody, /areas:\s*res\.matrix\s*\|\|\s*res\.areas\s*\|\|\s*\[\]/)
  assert.match(fnBody, /coverage_pct:\s*res\.coverage_score\s*\?\?\s*res\.coverage_pct\s*\?\?\s*0/)
})

test('existe un mapa de metadatos de estado con las 3 fases y su color/porcentaje', async () => {
  const source = await readSource()
  assert.match(source, /const METHODOLOGY_STATUS_META = \{/)
  assert.match(source, /COMPLETED:\s*\{[^}]*percent:\s*100/s)
  assert.match(source, /IN_PROGRESS:\s*\{[^}]*percent:\s*50/s)
  assert.match(source, /PENDING:\s*\{[^}]*percent:\s*0/s)
  assert.match(source, /function methodologyStatusMeta\(status\)/)
})

test('la franja resumen de 8 segmentos usa el color por disciplina, no solo COMPLETED', async () => {
  const source = await readSource()
  const checklistSection = source.slice(
    source.indexOf('Cobertura Metodológica de 8 Disciplinas'),
    source.indexOf('Asistente Táctico (pt-next)')
  )
  assert.match(checklistSection, /Resumen visual de cobertura por disciplina/)
  assert.match(checklistSection, /methodologyStatusMeta\(area\.status\)\.barClass/)
})

test('cada disciplina muestra una barra de progreso accesible ligada a su estado', async () => {
  const source = await readSource()
  const checklistSection = source.slice(
    source.indexOf('Cobertura Metodológica de 8 Disciplinas'),
    source.indexOf('Asistente Táctico (pt-next)')
  )
  assert.match(checklistSection, /role="progressbar"/)
  assert.match(checklistSection, /:aria-valuenow="methodologyStatusMeta\(area\.status\)\.percent"/)
  assert.match(checklistSection, /width:\s*methodologyStatusMeta\(area\.status\)\.percent \+ '%'/)
})

test('la insignia por disciplina ya no colapsa IN_PROGRESS y PENDING en el mismo estilo gris', async () => {
  const source = await readSource()
  const checklistSection = source.slice(
    source.indexOf('Cobertura Metodológica de 8 Disciplinas'),
    source.indexOf('Asistente Táctico (pt-next)')
  )
  assert.doesNotMatch(
    checklistSection,
    /area\.status === 'COMPLETED' \? 'bg-emerald-500\/10[^']*' : 'bg-slate-800 text-slate-400'/,
    'La condición binaria antigua ya no debe estar: IN_PROGRESS debe tener su propio estilo (ámbar)'
  )
  assert.match(checklistSection, /methodologyStatusMeta\(area\.status\)\.badgeClass/)
})
