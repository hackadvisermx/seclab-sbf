import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { createRequire } from 'node:module'
import { pathToFileURL } from 'node:url'
import { test } from 'node:test'
import { JSDOM } from 'jsdom'
const browser = new JSDOM('<body></body>', { url: 'http://localhost' })
for (const key of ['window','document','Document','Element','SVGElement','HTMLElement','Node','localStorage']) globalThis[key] = browser.window[key]
const { createApp, nextTick, reactive } = await import('vue')
const require = createRequire(import.meta.url)
const vueUrl = pathToFileURL(require.resolve('vue/dist/vue.runtime.esm-bundler.js')).href
const body = '## Descripción\nOriginal\n\n## Control negativo\nPrueba personalizada\n\n```http\nGET / HTTP/1.1\n```'
const finding = { source_sha256: 'd'.repeat(64), slug: 'legacy', filename: 'legacy.md', frontmatter: { title: 'Original', severity: 'INFO', status: 'PROVEN', asset: 'example.test', cvss_score: 0, cvss_vector: 'CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:N' }, artifact_refs: [{ path: 'recon/valid.txt', sha256: 'c'.repeat(64) }], verification_rationale: 'Operador reviso el fixture', body }
async function flush() { await nextTick(); await new Promise(r => setTimeout(r, 0)); await nextTick() }
async function mount(api, route = { params: { id: 'fixture', type: 'engagement' } }) {
  globalThis.fixtureFindingRoute = route
  globalThis.fixtureFindingApi = new Proxy(api, { get: (target, key) => target[key] || (async () => ({})) })
  const source = await readFile(new URL('../src/views/EngagementDetailView.vue', import.meta.url), 'utf8')
  const { parse, compileScript } = await import('@vue/compiler-sfc')
  const { descriptor } = parse(source)
  let code = compileScript(descriptor, { id: 'finding-edit', inlineTemplate: true }).content
    .replace(/from ["']vue["']/g, `from ${JSON.stringify(vueUrl)}`)
    .replace("import { useRoute, useRouter } from 'vue-router'", "const useRoute = () => globalThis.fixtureFindingRoute; const useRouter = () => ({ push() {} })")
    .replace("import { api } from '../api'", 'const api = globalThis.fixtureFindingApi')
  for (const name of ['report-security','scope-utils','recon-results','authorization-utils']) code = code.replace(`from '../${name}'`, `from ${JSON.stringify(new URL(`../src/${name}.js`, import.meta.url).href)}`)
  for (const name of ['DeleteProjectButton','HelpTooltip']) code = code.replace(new RegExp(`import ${name} from ['"]\\.\\./components/${name}\\.vue['"]`), `const ${name} = { render: () => null }`)
  const component = (await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}#${Math.random()}`)).default
  const root = document.createElement('div'); document.body.append(root)
  const app = createApp(component); app.component('router-link', { template: '<a><slot /></a>' }); app.mount(root); await flush()
  return { root, cleanup() { app.unmount(); root.remove() } }
}
async function clickText(root, text) {
  const button = [...root.querySelectorAll('button')].find(b => b.textContent.trim().includes(text))
  assert.ok(button, `Missing button ${text}`); button.click(); await flush()
}
async function mountDecision(api, route) {
  return mount({ getVaultKeys: async () => [], getFindings: async () => [], getArtifacts: async () => [],
    getLoot: async () => ({ credentials: [], files: [] }), ...api }, route)
}
const nextDecisionFixture = {
  decision_job: { run_id: 'a'.repeat(32), status: 'blocked', stage: 'probe', dry_run: false },
  next_step: { title: 'Revisar alcance tras el bloqueo', reason: 'Revisa el permiso antes de preparar otro plan.',
    action: { view: 'scope', label: 'Revisar alcance y autorización' }, command: null },
  prompt_available: false, prompt: '',
}

test('la siguiente decisión enlaza el bloqueo a Alcance sin comando ni prompt de ejecución', async () => {
  let prompts = 0
  const view = await mountDecision({ getNextStep: async (id, prompt) => { if (prompt) prompts++; return nextDecisionFixture } })
  try {
    await clickText(view.root, 'Metodología & Cobertura')
    const card = view.root.querySelector('[data-testid="next-decision"]')
    assert.match(card.textContent, /Revisar alcance tras el bloqueo/)
    assert.match(card.textContent, /aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/)
    assert.equal(card.querySelector('code'), null)
    const prompt = [...card.querySelectorAll('button')].find(el => el.textContent.includes('Generar Prompt'))
    assert.equal(prompt.disabled, true)
    prompt.click(); await flush(); assert.equal(prompts, 0)
    await clickText(card, 'Revisar alcance y autorización')
    assert.match(view.root.textContent, /Guardar Alcance/)
  } finally { view.cleanup() }
})

test('una respuesta tardía no reemplaza la decisión nueva ni deja un comando durante la carga', async () => {
  const requests = []
  const view = await mountDecision({ getNextStep: () => new Promise(resolve => requests.push(resolve)) })
  try {
    await clickText(view.root, 'Metodología & Cobertura')
    const card = view.root.querySelector('[data-testid="next-decision"]')
    assert.match(card.textContent, /Consultando/)
    assert.equal(card.querySelector('code'), null)
    const latest = requests.pop()
    latest(nextDecisionFixture); await flush()
    for (const resolve of requests) resolve({ next_step: { title: 'Obsoleto', command: 'pt-recon' }, prompt: 'Old' })
    await flush()
    assert.match(card.textContent, /Revisar alcance tras el bloqueo/)
    assert.doesNotMatch(card.textContent, /Obsoleto|pt-recon|Old/)
  } finally { view.cleanup() }
})

test('pedir prompt revalida el job y retira un prompt anterior si ahora hay fallo', async () => {
  let blocked = false
  const view = await mountDecision({ getNextStep: async (id, prompt) => blocked ? nextDecisionFixture :
    { next_step: { title: 'Paso legacy', command: 'pt-recon' }, prompt: prompt ? 'Prompt anterior' : '' } })
  try {
    await clickText(view.root, 'Metodología & Cobertura')
    const card = view.root.querySelector('[data-testid="next-decision"]')
    await clickText(card, 'Generar Prompt')
    assert.match(card.textContent, /Prompt anterior/)
    blocked = true
    await clickText(card, 'Generar Prompt')
    assert.match(card.textContent, /Revisar alcance tras el bloqueo/)
    assert.doesNotMatch(card.textContent, /Prompt anterior|pt-recon/)
    assert.equal([...card.querySelectorAll('button')].find(el => el.textContent.includes('Generar Prompt')).disabled, true)
  } finally { view.cleanup() }
})

test('un error al actualizar la decisión retira la recomendación previa y permite reintentar', async () => {
  let failure = false
  const view = await mountDecision({ getNextStep: async () => {
    if (failure) throw new Error('private backend details')
    return { next_step: { title: 'Paso legacy', command: 'pt-recon' } }
  } })
  try {
    await clickText(view.root, 'Metodología & Cobertura')
    const card = view.root.querySelector('[data-testid="next-decision"]')
    assert.match(card.textContent, /pt-recon/)
    failure = true; await clickText(card, 'Actualizar decisión')
    assert.match(card.textContent, /No se pudo consultar/)
    assert.doesNotMatch(card.textContent, /pt-recon|private backend/)
    failure = false; await clickText(card, 'Actualizar decisión')
    assert.match(card.textContent, /pt-recon/)
    assert.equal(card.querySelector('[role="alert"]'), null)
  } finally { view.cleanup() }
})
test('cambiar proyecto descarta recomendaciones y prompts pendientes del proyecto anterior', async () => {
  const route = reactive({ params: { id: 'fixture', type: 'engagement' } })
  const pending = []
  const view = await mountDecision({ getNextStep: id => id === 'fixture' ? new Promise(resolve => pending.push(resolve)) :
    Promise.resolve({ ...nextDecisionFixture, next_step: { ...nextDecisionFixture.next_step, title: 'Decisión del otro proyecto' } }) }, route)
  try {
    await clickText(view.root, 'Metodología & Cobertura')
    route.params.id = 'other'; await flush()
    for (const resolve of pending) resolve({ next_step: { title: 'Proyecto anterior', command: 'pt-recon' }, prompt: 'Prompt anterior' })
    await flush()
    const card = view.root.querySelector('[data-testid="next-decision"]')
    assert.match(card.textContent, /Decisión del otro proyecto/)
    assert.doesNotMatch(card.textContent, /Proyecto anterior|Prompt anterior|pt-recon/)
  } finally { view.cleanup() }
})

test('identidad persistente se muestra y se conserva al editar sin derivarla del título', async () => {
  const identity = 'abcdabcdabcd4bcd8bcdabcdabcdabcd'
  let saved
  const view = await mountDecision({ getFindings: async () => [{ ...finding, finding_id: identity }], saveFinding: async (id, payload) => { saved = payload } })
  try {
    await clickText(view.root, 'Hallazgos')
    assert.ok(view.root.querySelector('[data-testid="finding-identity"]').textContent.includes(identity))
    await clickText(view.root, 'Editar')
    await clickText(view.root, 'Guardar Ficha')
    assert.equal(saved.finding_id, identity)
    assert.equal(saved.body, body)
  } finally { view.cleanup() }
  const legacy = await mountDecision({ getFindings: async () => [finding] })
  try {
    await clickText(legacy.root, 'Hallazgos')
    assert.match(legacy.root.querySelector('[data-testid="finding-identity"]').textContent, /No registrada/)
  } finally { legacy.cleanup() }
})

test('editar una ficha conserva Markdown completo, fija el slug y envía solo el cuerpo original', async () => {
  let saved
  const view = await mount({ getVaultKeys: async () => [], getFindings: async () => [finding],
    getArtifacts: async () => [], getLoot: async () => ({ credentials: [], files: [] }), saveFinding: async (id, payload) => { saved = JSON.parse(JSON.stringify(payload)) } })
  try {
    await clickText(view.root, 'Hallazgos')
    await clickText(view.root, 'Editar')
    const editor = view.root.querySelector('[data-testid="finding-markdown"]')
    assert.equal(editor.value, body)
    for (const metric of ['C', 'I', 'A']) assert.equal(view.root.querySelector(`[data-testid="cvss-${metric}"]`).value, 'N')
    assert.equal(view.root.querySelector('input[placeholder="idor-user-profile, sqli-login"]').readOnly, true)
    editor.closest('form').dispatchEvent(new browser.window.Event('submit', { bubbles: true, cancelable: true }))
    await flush()
    assert.equal(saved.cvss_score, 0)
    assert.equal(saved.severity, 'INFO')
    assert.equal(saved.body, body)
    assert.equal(saved.description, '')
    assert.equal(saved.slug, 'legacy')
  } finally { view.cleanup() }
})

test('metodología muestra el contrato next_step y genera texto de prompt', async () => {
  const view = await mount({ getVaultKeys: async () => [], getFindings: async () => [],
    getArtifacts: async () => [], getLoot: async () => ({ credentials: [], files: [] }),
    getChecklist: async () => ({ matrix: [], coverage_score: 0 }),
    getNextStep: async (id, prompt) => ({ next_step: { title: 'Definir alcance', reason: 'Falta autorización', command: 'pt-scope show' }, ...(prompt ? { prompt: 'SYSTEM PROMPT: revisar alcance' } : {}) }) })
  try {
    await clickText(view.root, 'Metodología & Cobertura')
    assert.match(view.root.textContent, /Definir alcance/)
    assert.match(view.root.textContent, /Falta autorización/)
    assert.match(view.root.textContent, /pt-scope show/)
    await clickText(view.root, 'Generar Prompt Táctico')
    assert.equal(view.root.querySelector('pre').textContent.trim(), 'SYSTEM PROMPT: revisar alcance')
  } finally { view.cleanup() }
})

test('avance en vivo muestra comando y salida provisional; cancelado no se presenta en ejecución', async () => {
  const view = await mount({ getVaultKeys: async () => [], getFindings: async () => [],
    getArtifacts: async () => [], getLoot: async () => ({ credentials: [], files: [] }),
    getReconStatus: async () => ({ job: { status: 'cancelled' }, progress: { stage: 'subdomains', completed_stages: [], total_stages: 4,
      command: 'subfinder -d example.test -silent', command_status: 'running', recent_output: ['candidate.example.test'], events: [] } }) })
  try {
    await clickText(view.root, 'Reconocimiento')
    const panel = view.root.querySelector('[data-testid="recon-live-progress"]')
    assert.match(panel.textContent, /subfinder -d example.test/)
    assert.match(panel.textContent, /candidate.example.test/)
    assert.match(panel.textContent, /provisional/)
    assert.match(panel.textContent, /Interrumpida/)
    assert.doesNotMatch(panel.textContent, /Si la herramienta trabaja en silencio/)
  } finally { view.cleanup() }
})

test('el editor persiste vigencia y permiso pasivo sin activar permiso activo', async () => {
  let saved
  const scope = { scope: { in_scope: { domains: ['example.test'] }, out_of_scope: {} } }
  const view = await mount({ getScope: async () => scope, getVaultKeys: async () => [],
    getFindings: async () => [], getArtifacts: async () => [], getLoot: async () => ({ credentials: [], files: [] }),
    updateScope: async (id, payload) => { saved = structuredClone(payload); Object.assign(scope, saved) } })
  try {
    const fields = view.root.querySelector('fieldset')
    assert.ok(fields)
    const [passive, active] = fields.querySelectorAll('input[type=checkbox]')
    assert.equal(passive.checked, false)
    assert.equal(active.checked, false)
    const reference = fields.querySelector('input[type=text]')
    reference.value = 'Permiso de fixture'
    reference.dispatchEvent(new window.Event('input', { bubbles: true }))
    const [start, end] = fields.querySelectorAll('input[type=datetime-local]')
    start.value = '2000-01-01T00:00'
    end.value = '2099-01-01T00:00'
    for (const field of [start, end]) field.dispatchEvent(new window.Event('input', { bubbles: true }))
    passive.checked = true
    passive.dispatchEvent(new window.Event('change', { bubbles: true }))
    await clickText(view.root, 'Guardar Alcance')
    assert.equal(saved.authorization.reference, 'Permiso de fixture')
    assert.equal(saved.authorization.valid_from, new Date(start.value).toISOString())
    assert.equal(saved.authorization.allow_passive, true)
    assert.equal(saved.authorization.allow_active, false)
    assert.deepEqual(saved.scope.in_scope.domains, ['example.test'])
  } finally { view.cleanup() }
})


test('guardar espera la carga del contrato y un fallo permite reintentar sin sobrescribir', async () => {
  let resolveScope, writes = 0
  let response = new Promise(resolve => { resolveScope = resolve })
  const view = await mount({ getScope: () => response, getVaultKeys: async () => [], getFindings: async () => [],
    getArtifacts: async () => [], getLoot: async () => ({ credentials: [], files: [] }),
    updateScope: async () => { writes++ } })
  try {
    const save = () => [...view.root.querySelectorAll('button')].find(b => b.textContent.includes('Guardar Alcance'))
    assert.equal(save().disabled, true)
    assert.equal(view.root.querySelector('fieldset').disabled, true)
    save().click(); await flush(); assert.equal(writes, 0)
    resolveScope({ scope: { in_scope: { domains: ['example.test'] } } }); await flush()
    assert.equal(save().disabled, false)
    response = Promise.reject(new Error('fixture unavailable'))
    await clickText(view.root, 'Guardar Alcance')
    assert.equal(writes, 1)
    assert.equal(save().disabled, true)
    assert.match(view.root.textContent, /No se pudo cargar el contrato/)
    response = Promise.resolve({ scope: { in_scope: { domains: ['example.test'] } } })
    await clickText(view.root, 'Reintentar carga de alcance')
    assert.equal(save().disabled, false)
    assert.equal(writes, 1)
  } finally { view.cleanup() }
})


test('nueva ficha abre como CANDIDATE y una confirmación explícita no cambia la siguiente', async () => {
  const view = await mount({ getScope: async () => ({}), getVaultKeys: async () => [], getFindings: async () => [],
    getArtifacts: async () => [], getLoot: async () => ({ credentials: [], files: [] }) })
  const status = () => [...view.root.querySelectorAll('select')].find(el => el.querySelector('option[value="CANDIDATE"]'))
  try {
    await clickText(view.root, 'Hallazgos')
    await clickText(view.root, 'Nueva Ficha')
    assert.equal(status().value, 'CANDIDATE')
    assert.match(view.root.textContent, /ejemplos de una plantilla no demuestran/)
    status().value = 'PROVEN'; status().dispatchEvent(new window.Event('change', { bubbles: true })); await flush()
    await clickText(view.root, 'Cancelar')
    await clickText(view.root, 'Nueva Ficha')
    assert.equal(status().value, 'CANDIDATE')
  } finally { view.cleanup() }
})


test('historial muestra estados, origen legado y páginas sin duplicar jobs', async () => {
  const calls = []
  const job = (run_id, status, origin = 'dashboard') => ({ run_id, status, origin, stage: 'probe', dry_run: status === 'simulated', started_at: '2026-10-08T00:00:00Z', finished_at: '2026-10-08T00:01:00Z', scope_revision: null })
  const view = await mount({ getVaultKeys: async () => [], getFindings: async () => [], getArtifacts: async () => [],
    getLoot: async () => ({ credentials: [], files: [] }),
    getReconHistory: async (id, type, before) => {
      calls.push({ id, type, before })
      return before ? { jobs: [job('second', 'cancelled'), job('third', 'interrupted', 'legacy-current')], next_cursor: null }
        : { jobs: [job('first', 'simulated'), job('second', 'cancelled')], next_cursor: 'second' }
    } })
  try {
    await clickText(view.root, 'Reconocimiento')
    const panel = view.root.querySelector('[data-testid=recon-history]')
    assert.match(panel.textContent, /SIMULACIÓN/)
    assert.match(panel.textContent, /Simulado/)
    assert.match(panel.textContent, /Cancelado/)
    assert.match(panel.textContent, /no guarda copias de outputs anteriores/)
    await clickText(view.root, 'Cargar ejecuciones anteriores')
    assert.equal(panel.querySelectorAll('li').length, 3)
    assert.match(panel.textContent, /Interrumpido/)
    assert.match(panel.textContent, /Registro anterior importado/)
    assert.ok(calls.some(call => call.id === 'fixture' && call.type === 'engagement' && call.before === 'second'))
  } finally { view.cleanup() }
})

test('historial conserva resultados por job separados del workspace actual y distingue métricas previas', async () => {
  const snapshot = (count, source) => ({ recorded_at: '2026-10-09T12:00:00Z', metrics_source: source,
    metrics: { subdomains_count: 0, live_hosts_count: 0, urls_count: count, js_files_count: 0 },
    stages: [{ stage: 'urls', status: source === 'artifacts' ? 'completed' : 'failed',
      counts: source === 'artifacts' ? { urls_count: count, js_files_count: 0 } : {}, patterns: {} }] })
  const jobs = [{ run_id: 'earlier', status: 'completed', stage: 'urls', result_summary: snapshot(2, 'artifacts') },
    { run_id: 'blocked', status: 'blocked', stage: 'urls', result_summary: snapshot(5, 'previous_artifacts') },
    { run_id: 'simulation', status: 'simulated', stage: 'urls', dry_run: true, result_summary: null },
    { run_id: 'legacy', status: 'completed', stage: 'probe', result_summary: null }]
  const view = await mount({ getVaultKeys: async () => [], getFindings: async () => [], getArtifacts: async () => [],
    getLoot: async () => ({ credentials: [], files: [] }),
    getReconStatus: async () => ({ job: { status: 'completed' }, summary: { urls_count: 999 } }),
    getReconHistory: async () => ({ jobs, next_cursor: null }) })
  try {
    await clickText(view.root, 'Reconocimiento')
    const rows = view.root.querySelector('[data-testid=recon-history]').querySelectorAll('li')
    assert.match(rows[0].textContent, /URLs: 2/)
    assert.match(rows[0].textContent, /pueden incluir etapas que no se ejecutaron/)
    assert.doesNotMatch(rows[0].textContent, /999|URLs: 5/)
    assert.match(rows[0].textContent, /Resumen anterior: origen de etapa no registrado/)
    assert.doesNotMatch(rows[0].textContent, /Completada en este job/)
    assert.match(rows[1].textContent, /URLs: 5/)
    assert.match(rows[1].textContent, /artefactos previos; no acreditan resultados nuevos/)
    assert.match(rows[2].textContent, /simulación no genera resultados/)
    assert.match(rows[3].textContent, /Sin resumen de resultados conservado/)
  } finally { view.cleanup() }
})

test('historial distingue etapa recuperada con origen, intento actual y origen anterior desconocido', async () => {
  const snapshot = (origin, runId) => ({ schema_version: 2, recorded_at: '2026-10-10T12:00:00Z', metrics_source: 'previous_artifacts',
    metrics: { subdomains_count: 1, live_hosts_count: 0, urls_count: 0, js_files_count: 0 }, stages: [
      { stage: 'subdomains', status: 'completed', execution: 'recovered', origin_run_id: origin, counts: { in_scope_count: 1 }, patterns: {} },
      { stage: 'probe', status: 'failed', execution: 'current', origin_run_id: runId, counts: {}, patterns: {} },
    ] })
  const jobs = [{ run_id: 'b'.repeat(32), status: 'failed', stage: 'all', result_summary: snapshot('a'.repeat(32), 'b'.repeat(32)) },
    { run_id: 'c'.repeat(32), status: 'failed', stage: 'all', result_summary: snapshot(null, 'c'.repeat(32)) }]
  const view = await mountDecision({ getReconHistory: async () => ({ jobs, next_cursor: null }) })
  try {
    await clickText(view.root, 'Reconocimiento')
    const rows = view.root.querySelector('[data-testid=recon-history]').querySelectorAll('li')
    const origin = [...rows[0].querySelectorAll('p')].find(p => p.textContent.includes('Run de origen'))
    assert.match(origin.textContent, /no se ejecutó en este job/)
    assert.match(origin.textContent, /aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/)
    assert.doesNotMatch(origin.textContent, /bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb/)
    assert.match(rows[0].textContent, /Intentada en este job/)
    assert.match(rows[1].textContent, /Run de origen: No registrado/)
  } finally { view.cleanup() }
})

const reviewableJob = () => ({ run_id: 'a'.repeat(32), status: 'blocked', stage: 'probe', dry_run: false,
  started_at: '2026-10-09T00:00:00Z', finished_at: '2026-10-09T00:01:00Z',
  outcome_revision: 'b'.repeat(64), outcome_review: null })

test('registrar revisión exige decisión explícita y conserva bloqueo sin ejecutar ni cambiar alcance', async () => {
  let job = reviewableJob(), reviews = 0, launches = 0, saves = 0
  const view = await mountDecision({ getReconStatus: async () => ({ job }),
    getReconHistory: async () => ({ jobs: [job], next_cursor: null }),
    getNextStep: async () => nextDecisionFixture,
    runRecon: async () => { launches++ }, updateScope: async () => { saves++ },
    reviewReconOutcome: async (id, payload, type) => {
      assert.equal(id, 'fixture'); assert.equal(type, 'engagement')
      assert.deepEqual(payload, { run_id: job.run_id, expected_revision: job.outcome_revision })
      reviews++
      job = { ...job, outcome_review: { reviewed_at: '2026-10-09T00:02:00Z', decision: 'prepare_new_plan' } }
      return { success: true, job }
    } })
  try {
    await clickText(view.root, 'Reconocimiento')
    const form = view.root.querySelector('[data-testid=recon-outcome-form]')
    const button = form.querySelector('button')
    assert.equal(button.disabled, true)
    button.click(); await flush(); assert.equal(reviews, 0)
    const checkbox = form.querySelector('input')
    checkbox.checked = true; checkbox.dispatchEvent(new window.Event('change')); await flush()
    assert.equal(button.disabled, false)
    button.click(); await flush(); await flush()
    const review = view.root.querySelector('[data-testid=recon-outcome-review]')
    assert.match(review.textContent, /Resultado revisado por el operador/)
    assert.match(review.textContent, /Se conserva el estado Bloqueado/)
    assert.equal(reviews, 1); assert.equal(launches, 0); assert.equal(saves, 0)
    assert.equal(view.root.querySelector('[data-testid=recon-outcome-form]'), null)
  } finally { view.cleanup() }
})

test('un resultado obsoleto o activo no ofrece revisión y un rechazo obliga a revisar de nuevo', async () => {
  let job = reviewableJob(), reviews = 0
  const view = await mountDecision({ getReconStatus: async () => ({ job }),
    getReconHistory: async () => ({ jobs: [job], next_cursor: null }),
    reviewReconOutcome: async () => { reviews++; throw new Error('El job cambió. Actualiza el historial.') } })
  try {
    await clickText(view.root, 'Reconocimiento')
    const form = view.root.querySelector('[data-testid=recon-outcome-form]')
    form.querySelector('input').checked = true
    form.querySelector('input').dispatchEvent(new window.Event('change')); await flush()
    form.querySelector('button').click(); await flush(); await flush()
    assert.match(view.root.querySelector('[data-testid=recon-history]').textContent, /El job cambió/)
    assert.equal(view.root.querySelector('[data-testid=recon-outcome-review]'), null)
    assert.equal(view.root.querySelector('[data-testid=recon-outcome-form] button').disabled, true)
    assert.equal(reviews, 1)
    job = { ...job, status: 'running', finished_at: null }
    await clickText(view.root, 'Actualizar historial')
    assert.equal(view.root.querySelector('[data-testid=recon-outcome-form]'), null)
    job = { ...reviewableJob(), outcome_revision: 'c'.repeat(64) }
    await clickText(view.root, 'Actualizar historial')
    assert.equal(view.root.querySelector('[data-testid=recon-outcome-form]'), null)
  } finally { view.cleanup() }
})

test('una revisión que termina tras cambiar proyecto no aparece ni refresca el proyecto nuevo', async () => {
  const first = reviewableJob(), calls = []
  let finish
  const route = reactive({ params: { id: 'first', type: 'engagement' } })
  const view = await mountDecision({ getReconStatus: async id => ({ job: id === 'first' ? first : null }),
    getReconHistory: async id => { calls.push(id); return { jobs: id === 'first' ? [first] : [], next_cursor: null } },
    reviewReconOutcome: async () => new Promise(resolve => { finish = resolve }) }, route)
  try {
    await clickText(view.root, 'Reconocimiento')
    const form = view.root.querySelector('[data-testid=recon-outcome-form]')
    form.querySelector('input').checked = true
    form.querySelector('input').dispatchEvent(new window.Event('change')); await flush()
    form.querySelector('button').click(); await flush()
    route.params.id = 'second'; await flush(); await flush()
    const count = calls.length
    finish({ success: true, job: { ...first, outcome_review: { reviewed_at: '2026-10-09T00:02:00Z' } } })
    await flush(); await flush()
    assert.equal(calls.length, count)
    assert.equal(view.root.querySelector('[data-testid=recon-outcome-review]'), null)
    assert.match(view.root.querySelector('[data-testid=recon-history]').textContent, /Todavía no hay ejecuciones/)
  } finally { view.cleanup() }
})

test('un estado tardío de otro proyecto no habilita ni retira la revisión del proyecto actual', async () => {
  const old = reviewableJob(), current = { ...reviewableJob(), run_id: 'c'.repeat(32), outcome_revision: 'd'.repeat(64) }
  let finishOld
  const route = reactive({ params: { id: 'first', type: 'engagement' } })
  const view = await mountDecision({ getReconStatus: async id => id === 'first' ? new Promise(resolve => { finishOld = resolve }) : { job: current },
    getReconHistory: async id => ({ jobs: [id === 'first' ? old : current], next_cursor: null }) }, route)
  try {
    await clickText(view.root, 'Reconocimiento')
    route.params.id = 'second'; await flush(); await flush()
    assert.ok(view.root.querySelector('[data-testid=recon-outcome-form]'))
    finishOld({ job: old }); await flush(); await flush()
    assert.ok(view.root.querySelector('[data-testid=recon-outcome-form]'))
    assert.doesNotMatch(view.root.querySelector('[data-testid=recon-history]').textContent, /aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/)
  } finally { view.cleanup() }
})

test('historial comunica fallo de API y permite recuperar con reintento explícito', async () => {
  let unavailable = true
  const view = await mount({ getVaultKeys: async () => [], getFindings: async () => [], getArtifacts: async () => [],
    getLoot: async () => ({ credentials: [], files: [] }),
    getReconHistory: async () => { if (unavailable) throw new Error('Historial no disponible'); return { jobs: [], next_cursor: null } } })
  try {
    await clickText(view.root, 'Reconocimiento')
    const panel = view.root.querySelector('[data-testid=recon-history]')
    assert.match(panel.querySelector('[role=alert]').textContent, /Historial no disponible/)
    unavailable = false
    await clickText(view.root, 'Actualizar historial')
    assert.equal(panel.querySelector('[role=alert]'), null)
    assert.match(panel.textContent, /Todavía no hay ejecuciones registradas/)
  } finally { view.cleanup() }
})

test('un cambio de estado mientras se carga historial provoca una actualización posterior', async () => {
  let resolveInitial, calls = 0
  const initial = new Promise(resolve => { resolveInitial = resolve })
  const job = status => ({ run_id: 'same', status, stage: 'probe', dry_run: false, started_at: '2026-10-08T00:00:00Z' })
  const view = await mount({ getVaultKeys: async () => [], getFindings: async () => [], getArtifacts: async () => [],
    getLoot: async () => ({ credentials: [], files: [] }), getReconStatus: async () => ({ job: job('completed') }),
    getReconHistory: async () => ++calls === 1 ? initial : { jobs: [job('completed')], next_cursor: null } })
  try {
    resolveInitial({ jobs: [job('running')], next_cursor: null })
    await flush(); await flush()
    await clickText(view.root, 'Reconocimiento')
    assert.ok(calls >= 2)
    const panel = view.root.querySelector('[data-testid=recon-history]')
    assert.match(panel.textContent, /Completado/)
    assert.doesNotMatch(panel.textContent, /En ejecución/)
  } finally { view.cleanup() }
})


test('una respuesta tardía de otro proyecto no aparece en su historial', async () => {
  let resolveOld
  const pending = new Promise(resolve => { resolveOld = resolve })
  const route = reactive({ params: { id: 'first', type: 'engagement' } })
  const calls = []
  const view = await mount({ getVaultKeys: async () => [], getFindings: async () => [], getArtifacts: async () => [],
    getLoot: async () => ({ credentials: [], files: [] }),
    getReconHistory: async id => { calls.push(id); return id === 'first' ? pending : { jobs: [], next_cursor: null } } }, route)
  try {
    route.params.id = 'second'; await flush()
    resolveOld({ jobs: [{ run_id: 'old-project', status: 'completed', stage: 'probe', dry_run: false, started_at: '2026-10-08T00:00:00Z' }], next_cursor: null })
    await flush(); await flush()
    await clickText(view.root, 'Reconocimiento')
    const panel = view.root.querySelector('[data-testid=recon-history]')
    assert.doesNotMatch(panel.textContent, /old-project/)
    assert.ok(calls.includes('second'))
    assert.match(panel.textContent, /Todavía no hay ejecuciones registradas/)
  } finally { view.cleanup() }
})

test('bloqueo de Scope Guard muestra motivo, historial y revisión sin ejecutar ni autorizar', async () => {
  let scopeLoads = 0, launches = 0, saves = 0
  const job = { run_id: 'blocked-fixture', status: 'blocked', stage: 'probe', dry_run: false,
    started_at: '2026-10-08T00:00:00Z', finished_at: '2026-10-08T00:01:00Z', error: 'Falta permiso activo' }
  const view = await mount({ getVaultKeys: async () => [], getFindings: async () => [], getArtifacts: async () => [],
    getLoot: async () => ({ credentials: [], files: [] }),
    getScope: async () => { scopeLoads++; return {} },
    getReconStatus: async () => ({ job }), getReconHistory: async () => ({ jobs: [job], next_cursor: null }),
    runReconPipeline: async () => { launches++ }, updateScope: async () => { saves++ } })
  try {
    await clickText(view.root, 'Reconocimiento')
    const panel = view.root.querySelector('[data-testid=recon-blocked]')
    assert.match(panel.textContent, /Falta permiso activo/)
    assert.match(panel.textContent, /simula un plan nuevo/)
    assert.match(view.root.querySelector('[data-testid=recon-history]').textContent, /Bloqueado \(Scope Guard\)/)
    assert.doesNotMatch(view.root.textContent, /El reconocimiento falló/)
    const before = scopeLoads
    await clickText(view.root, 'Revisar alcance y autorización')
    assert.equal(view.root.querySelector('[data-testid=recon-blocked]'), null)
    assert.ok(scopeLoads > before)
    assert.equal(launches, 0)
    assert.equal(saves, 0)
  } finally { view.cleanup() }
})

test('vista ejecutiva usa cifras del reporte compilado y conserva su estado borrador', async () => {
  const content = '- **Fecha de Emisión:** 2025-12-01\n- **Crítica:** 0\n- **Alta:** 0\n- **Media:** 0\n- **Baja:** 0\n- **Informativa:** 0'
  const view = await mount({ getVaultKeys: async () => [], getFindings: async () => [finding],
    getArtifacts: async () => [], getLoot: async () => ({ credentials: [], files: [] }),
    previewReport: async () => ({ compiled: true, content }) })
  try {
    await clickText(view.root, 'Reporte (REPORT.md)')
    assert.deepEqual([...view.root.querySelectorAll('.report-printable div.text-center span.text-2xl')].map(el => el.textContent), ['0', '0', '0', '0', '0'])
    assert.match(view.root.textContent, /BORRADOR \/ PENDIENTE DE REVISIÓN/)
    assert.match(view.root.textContent, /2025-12-01/)
  } finally { view.cleanup() }
})

test('compilación bloqueada muestra el motivo sin sustituir el reporte anterior', async () => {
  let previews = 0
  const view = await mount({ getVaultKeys: async () => [], getFindings: async () => [],
    getArtifacts: async () => [], getLoot: async () => ({ credentials: [], files: [] }),
    previewReport: async () => { previews++; return { content: '# Reporte anterior' } },
    compileReport: async () => ({ success: false, log: 'Reporte bloqueado: activo fuera de alcance', content: '' }) })
  try {
    const before = previews
    await clickText(view.root, 'Compilar Reporte')
    assert.match(view.root.querySelector('[data-testid=report-error]').textContent, /fuera de alcance/)
    assert.equal(previews, before)
    await clickText(view.root, 'Reporte (REPORT.md)')
    assert.match(view.root.querySelector('.report-content-html').textContent, /Reporte anterior/)
  } finally { view.cleanup() }
})

test('vista previa bloqueada muestra targets/motivos y simulación revisada envía su revisión', async () => {
  let launched, simulate = false
  const preview = dry_run => ({ stages: [{ stage: 'probe', interaction: 'active', source: 'recon/subdomains.txt', targets: ['example.test'], targets_count: 1, discarded: [], discarded_count: 0, block_reasons: dry_run ? [] : ['Falta permiso activo'] }],
    dry_run, can_start: dry_run, plan_revision: 'a'.repeat(64), scope_revision: 'b'.repeat(64), operational_limits: { max_requests_per_second: 1, max_parallel_threads: 1, max_probe_targets: 1000 } })
  const view = await mount({ getVaultKeys: async () => [], getFindings: async () => [], getArtifacts: async () => [],
    getLoot: async () => ({ credentials: [], files: [] }),
    previewRecon: async (id, payload) => { simulate = payload.dry_run; return preview(simulate) },
    runRecon: async (id, payload) => { launched = payload; return { success: true } } })
  try {
    await clickText(view.root, 'Reconocimiento')
    const launch = () => [...view.root.querySelectorAll('button')].find(button => button.textContent.includes('Iniciar Reconocimiento'))
    assert.equal(launch().disabled, true)
    await clickText(view.root, 'Revisar plan sin tráfico')
    assert.match(view.root.querySelector('[data-testid=recon-preview]').textContent, /example.test/)
    assert.match(view.root.textContent, /Falta permiso activo/)
    assert.equal(launch().disabled, true)
    const mode = view.root.querySelector('#recon-dry-run'); mode.checked = true; mode.dispatchEvent(new window.Event('change', { bubbles: true })); await flush()
    assert.equal(view.root.querySelector('[data-testid=recon-preview]'), null)
    await clickText(view.root, 'Revisar plan sin tráfico')
    assert.equal(simulate, true)
    assert.equal(launch().disabled, false)
    await clickText(view.root, 'Iniciar Reconocimiento')
    assert.equal(launched.expected_plan, 'a'.repeat(64))
    assert.equal(launched.dry_run, true)
  } finally { view.cleanup() }
})

test('respuesta tardía de vista previa no habilita un modo distinto', async () => {
  let finish
  const view = await mount({ getVaultKeys: async () => [], getFindings: async () => [], getArtifacts: async () => [],
    getLoot: async () => ({ credentials: [], files: [] }), previewRecon: () => new Promise(resolve => { finish = resolve }) })
  try {
    await clickText(view.root, 'Reconocimiento')
    await clickText(view.root, 'Revisar plan sin tráfico')
    const mode = view.root.querySelector('#recon-dry-run'); mode.checked = true; mode.dispatchEvent(new window.Event('change', { bubbles: true })); await flush()
    finish({ can_start: true, stages: [], plan_revision: 'a'.repeat(64) }); await flush()
    assert.equal(view.root.querySelector('[data-testid=recon-preview]'), null)
    assert.equal([...view.root.querySelectorAll('button')].find(button => button.textContent.includes('Iniciar Reconocimiento')).disabled, true)
  } finally { view.cleanup() }
})

test('carga inicial tardía del alcance no borra una revisión más reciente', async () => {
  let finishScope
  const view = await mount({ getScope: () => new Promise(resolve => { finishScope = resolve }), getVaultKeys: async () => [],
    getFindings: async () => [], getArtifacts: async () => [], getLoot: async () => ({ credentials: [], files: [] }),
    previewRecon: async () => ({ stages: [], operational_limits: {}, can_start: true, plan_revision: 'a'.repeat(64) }) })
  try {
    await clickText(view.root, 'Reconocimiento')
    await clickText(view.root, 'Revisar plan sin tráfico')
    assert.ok(view.root.querySelector('[data-testid=recon-preview]'))
    finishScope({}); await flush()
    assert.ok(view.root.querySelector('[data-testid=recon-preview]'))
  } finally { view.cleanup() }
})


test('historial conserva revisión, permisos y límites sin confundir alcance ejecutado ni legacy', async () => {
  const plan = { schema_version: 1, checked_at: '2026-10-08T00:00:00Z', plan_revision: 'a'.repeat(64),
    scope_revision: 'b'.repeat(64), dry_run: true, authorization: { allow_passive: true, allow_active: false },
    operational_limits: { max_requests_per_second: 1, max_parallel_threads: 2, max_probe_targets: 100, probe_timeout_seconds: 8 },
    stages: [{ stage: 'probe', interaction: 'active', targets_count: 70, discarded_count: 1, targets_pending: true,
      targets: [{ host: 'reviewed.example.test', verdict: 'IN_SCOPE' }], discarded: [{ host: 'external.test', verdict: 'UNKNOWN' }] }] }
  const job = { run_id: 'reviewed', status: 'simulated', stage: 'probe', dry_run: true,
    started_at: '2026-10-08T00:00:00Z', scope_revision: 'c'.repeat(64), reviewed_plan: plan }
  const view = await mount({ getVaultKeys: async () => [], getFindings: async () => [], getArtifacts: async () => [],
    getLoot: async () => ({ credentials: [], files: [] }),
    getReconHistory: async () => ({ jobs: [job, { ...job, run_id: 'legacy', reviewed_plan: null }], next_cursor: null }) })
  try {
    await clickText(view.root, 'Reconocimiento')
    const panel = view.root.querySelector('[data-testid=recon-history]')
    assert.equal(panel.querySelectorAll('[data-testid=recon-history-review]').length, 1)
    assert.match(panel.textContent, /Plan revisado al iniciar/)
    assert.match(panel.textContent, /pasivo sí · activo no/)
    assert.match(panel.textContent, /La simulación no otorga permisos/)
    assert.match(panel.textContent, /8 s por petición/)
    assert.match(panel.textContent, /reviewed.example.test · IN_SCOPE/)
    assert.match(panel.textContent, /external.test · UNKNOWN/)
    assert.match(panel.textContent, /Targets finales pendientes/)
    assert.match(panel.textContent, /Muestra limitada a 50/)
    assert.match(panel.textContent, /rutas, consultas, fragmentos y credenciales/)
    assert.match(panel.textContent, /Sin plan revisado registrado/)
    for (const hash of ['a', 'b', 'c']) assert.ok(panel.textContent.includes(hash.repeat(64)))
  } finally { view.cleanup() }
})

test('Copiloto muestra validación no disponible y conserva la sugerencia como texto', async () => {
  let payload, executed = false
  const original = '<script>fixture-only</script> Revisa example.test.'
  const warning = '⚠️ Validación de alcance no disponible. La comprobación agotó su tiempo de espera.\nEsta respuesta sigue siendo una sugerencia sin comprobación de alcance.\n\n'
  const view = await mount({ getVaultKeys: async () => [], getFindings: async () => [], getArtifacts: async () => [],
    getLoot: async () => ({ credentials: [], files: [] }),
    runRecon: async () => { executed = true },
    sendCopilotChat: async data => { payload = structuredClone(data); return { content: warning + original, provider: 'fixture', model: 'fixture-model', latency_ms: 12 } } })
  try {
    await clickText(view.root, 'Copiloto Táctico')
    const input = view.root.querySelector('input[placeholder^="Pregunta al copiloto"]')
    input.value = 'Ayuda con evidencia'
    input.dispatchEvent(new browser.window.Event('input', { bubbles: true }))
    input.closest('form').dispatchEvent(new browser.window.Event('submit', { bubbles: true, cancelable: true }))
    await flush()
    assert.equal(payload.messages[0].content, 'Ayuda con evidencia')
    assert.match(view.root.textContent, /Validación de alcance no disponible/)
    assert.ok([...view.root.querySelectorAll('pre')].some(pre => pre.textContent === warning + original))
    assert.equal(view.root.querySelector('script'), null)
    assert.equal(executed, false)
    assert.match(view.root.textContent, /fixture-model/)
    assert.match(view.root.textContent, /no ejecuta comandos/)
  } finally { view.cleanup() }
})

test('artefacto muestra huella de bytes originales y distingue previsualización con reemplazos', async () => {
  const file = { name: 'raw.txt', rel_path: 'recon/raw.txt', size: 9 }
  const view = await mount({ getLoot: async () => ({ credentials: [], files: [] }), getFindings: async () => [], getVaultKeys: async () => [], getArtifacts: async () => [file], getArtifactContent: async () => ({ ...file,
    content: 'raw �', sha256: 'a'.repeat(64), modified: '2026-10-08T00:00:00+00:00', preview_status: 'decoded_with_replacement' }) })
  try {
    await clickText(view.root, 'Artefactos (recon/)')
    await clickText(view.root, 'raw.txt')
    const metadata = view.root.querySelector('[data-testid="artifact-fingerprint"]')
    assert.match(metadata.textContent, /9 bytes/)
    assert.ok(metadata.textContent.includes('a'.repeat(64)))
    assert.match(metadata.textContent, /sustituye bytes/)
    assert.match(metadata.textContent, /no acredita procedencia/)
    assert.equal(view.root.querySelector('pre').textContent, 'raw �')
  } finally { view.cleanup() }
})

test('una lectura tardía no mezcla hash o contenido con otro artefacto y error limpia metadata', async () => {
  let resolveFirst, rejectThird
  const first = new Promise(resolve => { resolveFirst = resolve })
  const third = new Promise((resolve, reject) => { rejectThird = reject })
  let calls = 0
  const files = ['one', 'two', 'three'].map(name => ({ name: name + '.txt', rel_path: `recon/${name}.txt`, size: 1 }))
  const view = await mount({ getLoot: async () => ({ credentials: [], files: [] }), getFindings: async () => [], getVaultKeys: async () => [], getArtifacts: async () => files, getArtifactContent: () => ++calls === 1 ? first : calls === 3 ? third : Promise.resolve({ ...files[1], content: 'two', sha256: 'b'.repeat(64), preview_status: 'complete' }) })
  try {
    await clickText(view.root, 'Artefactos (recon/)')
    await clickText(view.root, 'one.txt')
    const copy = () => [...view.root.querySelectorAll('button')].find(button => button.textContent.includes('Copiar Previsualización'))
    assert.equal(copy().disabled, true)
    await clickText(view.root, 'two.txt')
    resolveFirst({ ...files[0], content: 'one', sha256: 'a'.repeat(64), preview_status: 'complete' }); await flush()
    assert.equal(view.root.querySelector('pre').textContent, 'two')
    assert.ok(view.root.querySelector('[data-testid="artifact-fingerprint"]').textContent.includes('b'.repeat(64)))
    await clickText(view.root, 'three.txt')
    assert.equal(view.root.querySelector('[data-testid="artifact-fingerprint"]'), null)
    assert.equal(copy().disabled, true)
    rejectThird(new Error('El artefacto cambió; vuelve a seleccionarlo')); await flush()
    assert.match(view.root.querySelector('pre').textContent, /El artefacto cambió/)
    assert.equal(view.root.querySelector('[data-testid="artifact-fingerprint"]'), null)
  } finally { view.cleanup() }
})

test('cambiar carpeta descarta respuestas antiguas de listado y previsualización', async () => {
  let resolveFirst, resolvePreview
  const first = new Promise(resolve => { resolveFirst = resolve })
  const preview = new Promise(resolve => { resolvePreview = resolve })
  const file = { name: 'raw.txt', rel_path: 'fuzzing/raw.txt', size: 1 }
  const view = await mount({ getLoot: async () => ({ credentials: [], files: [] }), getFindings: async () => [], getVaultKeys: async () => [], getArtifacts: async (id, folder) => folder === 'recon' ? first : folder === 'fuzzing' ? [file] : [],
    getArtifactContent: () => preview })
  try {
    await clickText(view.root, 'Artefactos (recon/)')
    await clickText(view.root, 'fuzzing/')
    resolveFirst([{ name: 'old.txt', rel_path: 'recon/old.txt', size: 1 }]); await flush()
    assert.doesNotMatch(view.root.textContent, /old\.txt/)
    await clickText(view.root, 'raw.txt')
    await clickText(view.root, 'screenshots/')
    resolvePreview({ ...file, content: 'stale', sha256: 'a'.repeat(64) }); await flush()
    assert.equal(view.root.querySelector('[data-testid="artifact-fingerprint"]'), null)
    assert.doesNotMatch(view.root.textContent, /stale|raw\.txt/)
  } finally { view.cleanup() }
})

const artifactJob = (letter, hash = 'a'.repeat(64)) => ({ run_id: letter.repeat(32), status: 'completed', stage: 'urls',
  result_summary: { schema_version: 3, recorded_at: '2026-10-10T12:00:00Z', metrics_source: 'artifacts',
    metrics: { subdomains_count: 0, live_hosts_count: 0, urls_count: 1, js_files_count: 0 }, stages: [
      { stage: 'urls', status: 'completed', execution: 'current', origin_run_id: letter.repeat(32), counts: { urls_count: 1, js_files_count: 0 }, patterns: {}, failure_kind: null,
        artifact_capture: { status: 'recorded', refs: [{ path: 'recon/urls_all.txt', sha256: hash, size: 9 },
          { path: 'recon/js_files.txt', sha256: 'c'.repeat(64), size: 0 }] } },
    ] } })

test('historial compara versiones sin alterar referencia y distingue archivo ausente, límite y legacy', async () => {
  let mode = 'match'
  const job = artifactJob('b')
  const unavailable = artifactJob('c'); unavailable.result_summary.stages[0].artifact_capture = { status: 'unavailable', refs: [] }
  const legacy = artifactJob('d'); legacy.result_summary.schema_version = 2; delete legacy.result_summary.stages[0].artifact_capture
  const file = { rel_path: 'recon/urls_all.txt', name: 'urls_all.txt', size: 9 }
  const view = await mountDecision({ getReconHistory: async () => ({ jobs: [job, unavailable, legacy], next_cursor: null }), getArtifacts: async () => [file],
    getArtifactContent: async () => {
      if (mode === 'missing') throw new Error('Archivo no encontrado')
      return { ...file, content: 'fixture', preview_status: 'complete', sha256: mode === 'large' ? null : mode === 'changed' ? 'f'.repeat(64) : 'a'.repeat(64), size: mode === 'size' ? 10 : 9 }
    } })
  const compare = async () => { await clickText(view.root, 'Reconocimiento'); await clickText(view.root, 'Comparar archivo actual recon/urls_all.txt') }
  try {
    await compare()
    const box = () => view.root.querySelector('[data-testid="job-artifact-comparison"]')
    assert.match(box().textContent, /coincide con la registrada/)
    assert.ok(box().textContent.includes(job.run_id)); assert.ok(box().textContent.includes('a'.repeat(64)))
    assert.match(box().textContent, /Los bytes anteriores no se guardaron/)
    for (const current of ['changed', 'size', 'large', 'missing']) {
      mode = current; await compare()
      assert.ok(box().textContent.includes('a'.repeat(64)))
      assert.match(box().textContent, current === 'large' ? /no se puede comparar/ : current === 'missing' ? /No se pudo leer/ : /difiere de la registrada/)
      assert.equal(job.result_summary.stages[0].artifact_capture.refs[0].sha256, 'a'.repeat(64))
    }
    await clickText(view.root, 'urls_all.txt')
    assert.equal(box(), null)
    await clickText(view.root, 'Reconocimiento')
    assert.match(view.root.textContent, /Huellas no disponibles/)
    assert.match(view.root.textContent, /resumen anterior no conserva huellas/)
  } finally { view.cleanup() }
})

test('comparación conserva el job seleccionado y descarta lectura tardía al cambiar job o proyecto', async () => {
  let resolveFirst, calls = 0
  const first = new Promise(resolve => { resolveFirst = resolve })
  const jobs = [artifactJob('b'), artifactJob('c', 'c'.repeat(64))]
  const route = reactive({ params: { id: 'fixture', type: 'engagement' } })
  const view = await mountDecision({ getReconHistory: async () => ({ jobs, next_cursor: null }),
    getArtifactContent: () => ++calls === 1 ? first : Promise.resolve({ content: 'current c', sha256: 'c'.repeat(64), size: 9, preview_status: 'complete' }) }, route)
  try {
    await clickText(view.root, 'Reconocimiento')
    const firstRow = view.root.querySelector('[data-testid="recon-history"] li')
    await clickText(firstRow, 'Comparar archivo actual recon/urls_all.txt')
    assert.match(view.root.querySelector('[data-testid="job-artifact-comparison"]').textContent, /Leyendo/)
    await clickText(view.root, 'Reconocimiento')
    const secondRow = view.root.querySelectorAll('[data-testid="recon-history"] li')[1]
    await clickText(secondRow, 'Comparar archivo actual recon/urls_all.txt')
    resolveFirst({ content: 'stale b', sha256: 'a'.repeat(64), size: 9, preview_status: 'complete' }); await flush()
    const box = view.root.querySelector('[data-testid="job-artifact-comparison"]')
    assert.ok(box.textContent.includes(jobs[1].run_id)); assert.ok(!box.textContent.includes(jobs[0].run_id))
    assert.match(box.textContent, /coincide/); assert.doesNotMatch(view.root.textContent, /stale b/)
    route.params.id = 'other'; await flush()
    assert.equal(view.root.querySelector('[data-testid="job-artifact-comparison"]'), null)
  } finally { view.cleanup() }
})

test('editar conserva vínculos y solo añade la versión revisada explícitamente', async () => {
  const reference = { path: 'recon/kept.txt', sha256: 'a'.repeat(64) }
  let saved
  const view = await mount({ getLoot: async () => ({ credentials: [], files: [] }), getArtifacts: async () => [], getVaultKeys: async () => [],
    getFindings: async () => [{ ...finding, artifact_refs: [reference] }],
    getArtifactContent: async () => ({ content: 'fixture bytes', sha256: 'b'.repeat(64), fingerprint_status: 'available', preview_status: 'complete' }),
    saveFinding: async (id, payload) => { saved = JSON.parse(JSON.stringify(payload)) } })
  try {
    await clickText(view.root, 'Hallazgos')
    await clickText(view.root, 'Editar')
    const section = view.root.querySelector('[data-testid="finding-artifact-editor"]')
    assert.match(section.textContent, /recon\/kept.txt/)
    const input = section.querySelector('input')
    input.value = 'recon/new.txt'; input.dispatchEvent(new window.Event('input', { bubbles: true })); await flush()
    await clickText(section, 'Revisar artefacto')
    assert.match(section.textContent, /fixture bytes/)
    await clickText(section, 'Vincular versión revisada')
    await clickText(view.root, 'Guardar Ficha')
    assert.equal(saved.body, body)
    assert.deepEqual(saved.artifact_refs, [reference, { path: 'recon/new.txt', sha256: 'b'.repeat(64) }])
  } finally { view.cleanup() }
})

test('respuesta tardía del revisor no vincula otra ruta y referencias inválidas requieren descarte', async () => {
  let resolveRead, writes = 0
  const read = new Promise(resolve => { resolveRead = resolve })
  const view = await mount({ getLoot: async () => ({ credentials: [], files: [] }), getArtifacts: async () => [], getVaultKeys: async () => [],
    getFindings: async () => [{ ...finding, artifact_refs_error: 'Referencias inválidas', artifact_refs: [] }],
    getArtifactContent: () => read, saveFinding: async () => { writes++ } })
  try {
    await clickText(view.root, 'Hallazgos'); await clickText(view.root, 'Editar')
    const section = view.root.querySelector('[data-testid="finding-artifact-editor"]')
    await clickText(view.root, 'Guardar Ficha'); assert.equal(writes, 0)
    const input = section.querySelector('input')
    input.value = 'recon/one.txt'; input.dispatchEvent(new window.Event('input', { bubbles: true })); await flush()
    await clickText(section, 'Revisar artefacto')
    input.value = 'recon/two.txt'; input.dispatchEvent(new window.Event('input', { bubbles: true })); await flush()
    resolveRead({ content: 'stale', sha256: 'a'.repeat(64), fingerprint_status: 'available' }); await flush()
    assert.doesNotMatch(section.textContent, /stale|Vincular versión revisada/)
    await clickText(section, 'Descartar referencias inválidas')
    await clickText(view.root, 'Guardar Ficha'); assert.equal(writes, 0)
    const status = [...view.root.querySelectorAll('select')].find(el => el.querySelector('option[value="CANDIDATE"]'))
    status.value = 'CANDIDATE'; status.dispatchEvent(new window.Event('change', { bubbles: true })); await flush()
    await clickText(view.root, 'Guardar Ficha'); assert.equal(writes, 1)
  } finally { view.cleanup() }
})

test('confirmar exige activo, vínculo y motivo y conserva la decisión explícita', async () => {
  let saved
  const view = await mount({ getLoot: async () => ({ credentials: [], files: [] }), getArtifacts: async () => [], getVaultKeys: async () => [],
    getFindings: async () => [{ ...finding, frontmatter: { ...finding.frontmatter, status: 'CANDIDATE', asset: '' }, artifact_refs: [], verification_rationale: '' }],
    getArtifactContent: async () => ({ content: 'fixture', sha256: 'b'.repeat(64), fingerprint_status: 'available', preview_status: 'complete' }),
    saveFinding: async (id, payload) => { saved = JSON.parse(JSON.stringify(payload)) } })
  try {
    await clickText(view.root, 'Hallazgos'); await clickText(view.root, 'Editar')
    const form = view.root.querySelector('[data-testid="finding-markdown"]').closest('form')
    const status = [...form.querySelectorAll('select')].find(el => el.querySelector('option[value="CANDIDATE"]'))
    status.value = 'PROVEN'; status.dispatchEvent(new window.Event('change', { bubbles: true })); await flush()
    assert.match(form.textContent, /Indica el activo autorizado/)
    await clickText(view.root, 'Guardar Ficha'); assert.equal(saved, undefined)
    const asset = form.querySelector('input[placeholder="api.target.local/v1/profile"]')
    asset.value = 'example.test'; asset.dispatchEvent(new window.Event('input', { bubbles: true })); await flush()
    assert.match(form.textContent, /Vincula al menos un artefacto/)
    const path = form.querySelector('#finding-artifact-path')
    path.value = 'recon/raw.txt'; path.dispatchEvent(new window.Event('input', { bubbles: true })); await flush()
    await clickText(form, 'Revisar artefacto'); await clickText(form, 'Vincular versión revisada')
    assert.match(form.textContent, /Explica el motivo de verificación/)
    const rationale = form.querySelector('#finding-verification-rationale')
    rationale.value = 'Operador comparó el control sintético'; rationale.dispatchEvent(new window.Event('input', { bubbles: true })); await flush()
    await clickText(view.root, 'Guardar Ficha')
    assert.equal(saved.status, 'PROVEN')
    assert.equal(saved.verification_rationale, rationale.value)
    assert.equal(saved.body, body)
  } finally { view.cleanup() }
})

test('confirmación antigua incompleta muestra revisión pendiente y permite volver a candidato', async () => {
  let saved
  const view = await mount({ getLoot: async () => ({ credentials: [], files: [] }), getArtifacts: async () => [], getVaultKeys: async () => [],
    getFindings: async () => [{ ...finding, artifact_refs: [], verification_rationale: '', confirmation_error: 'Falta evidencia vinculada' }],
    saveFinding: async (id, payload) => { saved = JSON.parse(JSON.stringify(payload)) } })
  try {
    await clickText(view.root, 'Hallazgos')
    assert.match(view.root.textContent, /Revisión pendiente \(PROVEN\)/)
    await clickText(view.root, 'Editar')
    await clickText(view.root, 'Guardar Ficha'); assert.equal(saved, undefined)
    const status = [...view.root.querySelectorAll('select')].find(el => el.querySelector('option[value="CANDIDATE"]'))
    status.value = 'CANDIDATE'; status.dispatchEvent(new window.Event('change', { bubbles: true })); await flush()
    await clickText(view.root, 'Guardar Ficha')
    assert.equal(saved.status, 'CANDIDATE')
    assert.equal(saved.body, body)
  } finally { view.cleanup() }
})

test('abrir evidencia vinculada muestra diferencia sin actualizar la huella guardada', async () => {
  const reference = { path: 'recon/raw.txt', sha256: 'a'.repeat(64) }
  const view = await mount({ getLoot: async () => ({ credentials: [], files: [] }), getArtifacts: async () => [], getVaultKeys: async () => [],
    getFindings: async () => [{ ...finding, artifact_refs: [reference] }],
    getArtifactContent: async () => ({ content: 'changed', sha256: 'b'.repeat(64), fingerprint_status: 'available', preview_status: 'complete' }) })
  try {
    await clickText(view.root, 'Hallazgos'); await clickText(view.root, 'Abrir recon/raw.txt')
    assert.match(view.root.textContent, /no coincide con la vinculada/)
    assert.match(view.root.textContent, /no se ha cambiado/)
    await clickText(view.root, 'Hallazgos')
    assert.ok(view.root.querySelector('[data-testid="finding-artifact-ref"]').textContent.includes('a'.repeat(64)))
  } finally { view.cleanup() }
})


test('el enlace fuente del reporte abre el visor con su hash sin guardar ni ejecutar', async () => {
  const sha = 'c'.repeat(64)
  const reads = []
  let writes = 0
  const view = await mountDecision({
    previewReport: async () => ({ content: `[Ficha fuente](./evidence/ficha.md#sha256=${sha})` }),
    getArtifacts: async () => [],
    getArtifactContent: async (id, path) => { reads.push([id, path]); return { content: 'Ficha actual', sha256: 'd'.repeat(64), fingerprint_status: 'available' } },
    saveFinding: async () => { writes++ }, runRecon: async () => { writes++ },
  })
  try {
    await clickText(view.root, 'Reporte (REPORT.md)')
    const anchor = view.root.querySelector('.prose-report a')
    assert.ok(anchor)
    const event = new window.MouseEvent('click', { bubbles: true, cancelable: true, button: 0 })
    assert.equal(anchor.dispatchEvent(event), false)
    await flush(); await flush()
    assert.deepEqual(reads, [['fixture', 'evidence/ficha.md']])
    assert.match(view.root.textContent, /versión actual no coincide/)
    assert.match(view.root.textContent, /Ficha actual/)
    assert.equal(writes, 0)
  } finally { view.cleanup() }
})

test('orientación local funciona sin IA, respeta el bloqueo y solo abre revisión', async () => {
  let chats = 0, writes = 0
  const prompts = []
  const view = await mountDecision({ getNextStep: async (id, prompt) => { prompts.push(prompt); return nextDecisionFixture },
    sendCopilotChat: async () => { chats++ }, runRecon: async () => { writes++ }, updateScope: async () => { writes++ } })
  try {
    await clickText(view.root, 'Copiloto Táctico')
    await clickText(view.root, 'Orientación local sin IA')
    const card = view.root.querySelector('[data-testid=copilot-local-guidance]')
    assert.ok(card)
    assert.match(card.textContent, /Reglas locales/)
    assert.match(card.textContent, /Revisar alcance tras el bloqueo/)
    assert.match(card.textContent, /aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/)
    assert.equal(card.querySelector('code'), null)
    assert.ok(prompts.length); assert.ok(prompts.every(value => value === false))
    await clickText(card, 'Revisar alcance y autorización')
    assert.match(view.root.textContent, /Guardar Alcance/)
    assert.equal(chats, 0); assert.equal(writes, 0)
  } finally { view.cleanup() }
})

for (const failure of ['timeout', 'sin proveedor', 'contenido vacío', 'contenido inválido']) test(`fallo IA (${failure}) ofrece decisión local fresca y no reintenta proveedor`, async () => {
  let changed = false, chats = 0
  const view = await mountDecision({ getNextStep: async () => changed ? nextDecisionFixture : { next_step: { title: 'Decisión anterior', command: 'pt-recon old' } },
    sendCopilotChat: async () => { chats++; changed = true; if (failure === 'contenido vacío') return { content: '' }; if (failure === 'contenido inválido') return { content: {} }; throw new Error(failure) } })
  try {
    await clickText(view.root, 'Copiloto Táctico')
    const input = view.root.querySelector('input[placeholder^="Pregunta al copiloto"]')
    input.value = 'Ayuda'; input.dispatchEvent(new window.Event('input')); await flush()
    await clickText(view.root, 'Enviar Consulta'); await flush()
    const card = view.root.querySelector('[data-testid=copilot-local-guidance]')
    assert.ok(card)
    assert.match(card.textContent, /Revisar alcance tras el bloqueo/)
    assert.doesNotMatch(card.textContent, /Decisión anterior|pt-recon old/)
    assert.match(view.root.textContent, /Error del Copiloto/)
    assert.equal(chats, 1)
  } finally { view.cleanup() }
})

test('fallo de recomendador local retira la sugerencia previa y permite reintentar', async () => {
  let failed = false
  const view = await mountDecision({ getNextStep: async () => { if (failed) throw new Error('unavailable'); return { next_step: { title: 'Recomendación anterior', command: 'old command' } } } })
  try {
    await clickText(view.root, 'Copiloto Táctico')
    await clickText(view.root, 'Orientación local sin IA')
    failed = true
    await clickText(view.root, 'Orientación local sin IA')
    const card = view.root.querySelector('[data-testid=copilot-local-guidance]')
    assert.match(card.textContent, /No se pudo consultar/)
    assert.doesNotMatch(card.textContent, /Recomendación anterior|old command/)
    assert.equal(card.querySelector('code'), null)
    failed = false
    await clickText(view.root, 'Orientación local sin IA')
    assert.match(card.textContent, /Recomendación anterior/)
  } finally { view.cleanup() }
})

for (const rejected of [false, true]) test(`respuesta IA tardía (${rejected ? 'error' : 'éxito'}) no activa orientación de otro proyecto`, async () => {
  let resolveChat, rejectChat
  const route = reactive({ params: { id: 'fixture', type: 'engagement' } })
  const view = await mountDecision({ getNextStep: async () => nextDecisionFixture,
    sendCopilotChat: () => new Promise((resolve, reject) => { resolveChat = resolve; rejectChat = reject }) }, route)
  try {
    await clickText(view.root, 'Copiloto Táctico')
    const input = view.root.querySelector('input[placeholder^="Pregunta al copiloto"]')
    input.value = 'Consulta antigua'; input.dispatchEvent(new window.Event('input')); await flush()
    await clickText(view.root, 'Enviar Consulta')
    route.params.id = 'other'; await flush()
    if (rejected) rejectChat(new Error('Fallo antiguo')); else resolveChat({ content: 'Respuesta antigua' })
    await flush(); await flush()
    assert.equal(view.root.querySelector('[data-testid=copilot-local-guidance]'), null)
    assert.doesNotMatch(view.root.textContent, /Consulta antigua|Respuesta antigua|Fallo antiguo|Analizando evidencias/)
  } finally { view.cleanup() }
})


test('respuesta local inválida no conserva comando ni aparenta una decisión disponible', async () => {
  let invalid = false
  const view = await mountDecision({ getNextStep: async () => invalid ? null : nextDecisionFixture })
  try {
    await clickText(view.root, 'Copiloto Táctico')
    await clickText(view.root, 'Orientación local sin IA')
    invalid = true
    await clickText(view.root, 'Orientación local sin IA')
    const card = view.root.querySelector('[data-testid=copilot-local-guidance]')
    assert.match(card.textContent, /No se pudo consultar/)
    assert.doesNotMatch(card.textContent, /Revisar alcance tras el bloqueo/)
    assert.equal(card.querySelector('code'), null)
  } finally { view.cleanup() }
})

for (const key of ['id', 'type']) test(`inspector de contexto descarta respuesta tras cambiar ${key}`, async () => {
  const route = reactive({ params: { id: 'fixture', type: 'engagement' } })
  const pending = []
  const view = await mountDecision({ getCopilotContext: (id, agent, type) => new Promise(resolve => pending.push({ id, agent, type, resolve })) }, route)
  try {
    await clickText(view.root, 'Copiloto Táctico')
    await clickText(view.root, 'Ver Contexto pt-context')
    assert.match(view.root.querySelector('pre').textContent, /Generando contexto/)
    route.params[key] = key === 'id' ? 'other' : 'challenge'; await flush()
    pending[0].resolve({ context: 'CONTEXTO PRIVADO ANTERIOR' }); await flush()
    assert.equal(view.root.querySelector('pre'), null)
    await clickText(view.root, 'Ver Contexto pt-context')
    pending[1].resolve({ context: 'Contexto actual' }); await flush()
    assert.equal(pending[1][key], route.params[key])
    assert.equal(view.root.querySelector('pre').textContent, 'Contexto actual')
    assert.doesNotMatch(view.root.textContent, /PRIVADO ANTERIOR/)
  } finally { view.cleanup() }
})

test('cambiar especialidad cierra contexto y no mezcla una respuesta tardía', async () => {
  const pending = []
  const view = await mountDecision({ getCopilotContext: (id, agent) => new Promise(resolve => pending.push({ agent, resolve })) })
  try {
    await clickText(view.root, 'Copiloto Táctico')
    await clickText(view.root, 'Ver Contexto pt-context')
    const select = view.root.querySelector('select')
    select.value = 'auth-agent'; select.dispatchEvent(new window.Event('change')); await flush()
    pending[0].resolve({ context: 'Especialidad anterior' }); await flush()
    assert.equal(view.root.querySelector('pre'), null)
    await clickText(view.root, 'Ver Contexto pt-context')
    assert.equal(pending[1].agent, 'auth-agent')
    pending[1].resolve({ context: 'Especialidad actual' }); await flush()
    assert.equal(view.root.querySelector('pre').textContent, 'Especialidad actual')
  } finally { view.cleanup() }
})

test('error de contexto se muestra y la consulta bloqueada permite orientación local', async () => {
  const error = 'Contexto no disponible: el generador falló. Revisa los archivos locales y reintenta.'
  const view = await mountDecision({ getCopilotContext: async () => { throw new Error(error) }, sendCopilotChat: async () => { throw new Error(error) }, getNextStep: async () => nextDecisionFixture })
  try {
    await clickText(view.root, 'Copiloto Táctico')
    await clickText(view.root, 'Ver Contexto pt-context')
    assert.equal(view.root.querySelector('pre').textContent, 'Error al cargar contexto: ' + error)
    await clickText(view.root, 'Cerrar')
    const input = view.root.querySelector('input[placeholder^="Pregunta al copiloto"]')
    input.value = 'Ayuda'; input.dispatchEvent(new window.Event('input')); await flush()
    await clickText(view.root, 'Enviar Consulta'); await flush()
    assert.match(view.root.querySelector('[data-testid=copilot-local-guidance]').textContent, /Revisar alcance tras el bloqueo/)
    assert.match(view.root.textContent, /Contexto no disponible/)
  } finally { view.cleanup() }
})

test('conflicto de versión conserva borrador y exige revisar la fuente antes de reintentar', async () => {
  const sent = []
  const latest = { ...finding, source_sha256: 'e'.repeat(64), body: 'Cambio guardado en otra vista', frontmatter: { ...finding.frontmatter, title: 'Título actual' } }
  const view = await mountDecision({ getFindings: async () => [finding], getFinding: async () => latest,
    saveFinding: async (id, payload) => { sent.push(JSON.parse(JSON.stringify(payload))); if (sent.length === 1) throw new Error('La ficha cambió desde que la abriste; no se sobrescribió.') } })
  try {
    await clickText(view.root, 'Hallazgos'); await clickText(view.root, 'Editar')
    const editor = view.root.querySelector('[data-testid="finding-markdown"]')
    editor.value = 'Mi borrador revisado'; editor.dispatchEvent(new window.Event('input')); await flush()
    await clickText(view.root, 'Guardar Ficha')
    assert.equal(sent[0].expected_source_sha256, finding.source_sha256)
    assert.equal(editor.value, 'Mi borrador revisado')
    assert.match(view.root.querySelector('[data-testid="finding-save-error"]').textContent, /no se sobrescribió/)
    await clickText(view.root, 'Ver ficha actual sin reemplazar borrador')
    assert.match(view.root.querySelector('[data-testid="finding-current-version"]').textContent, /Cambio guardado en otra vista/)
    assert.equal(editor.value, 'Mi borrador revisado')
    assert.equal(sent.length, 1)
    await clickText(view.root, 'Revisé los cambios; usar esta versión como base')
    assert.equal(sent.length, 1)
    await clickText(view.root, 'Guardar Ficha')
    assert.equal(sent[1].expected_source_sha256, latest.source_sha256)
    assert.equal(sent[1].body, 'Mi borrador revisado')
    assert.equal(view.root.querySelector('[data-testid="finding-markdown"]'), null)
  } finally { view.cleanup() }
})

test('sin versión de lectura la UI no guarda; puede revisar fuente sin perder borrador', async () => {
  let writes = 0
  const view = await mountDecision({ getFindings: async () => [{ ...finding, source_sha256: null }],
    getFinding: async () => finding, saveFinding: async () => { writes++ } })
  try {
    await clickText(view.root, 'Hallazgos'); await clickText(view.root, 'Editar'); await clickText(view.root, 'Guardar Ficha')
    assert.equal(writes, 0)
    assert.match(view.root.querySelector('[data-testid="finding-save-error"]').textContent, /Falta la versión/)
    await clickText(view.root, 'Ver ficha actual sin reemplazar borrador')
    await clickText(view.root, 'Revisé los cambios; usar esta versión como base')
    await clickText(view.root, 'Guardar Ficha'); assert.equal(writes, 1)
  } finally { view.cleanup() }
})

for (const key of ['id', 'type']) test(`cambiar ${key} cierra el editor y descarta guardado pendiente`, async () => {
  const route = reactive({ params: { id: 'fixture', type: 'engagement' } })
  let finish, writes = 0
  const view = await mountDecision({ getFindings: async () => [finding], saveFinding: () => { writes++; return new Promise(resolve => { finish = resolve }) } }, route)
  try {
    await clickText(view.root, 'Hallazgos'); await clickText(view.root, 'Editar'); await clickText(view.root, 'Guardar Ficha')
    await clickText(view.root, 'Guardando Ficha'); assert.equal(writes, 1)
    route.params[key] = key === 'id' ? 'other' : 'reto'; await flush()
    assert.equal(view.root.querySelector('[data-testid="finding-markdown"]'), null)
    await clickText(view.root, 'Editar')
    finish(); await flush()
    assert.ok(view.root.querySelector('[data-testid="finding-markdown"]'))
    assert.equal(writes, 1)
  } finally { view.cleanup() }
})

test('comparación tardía no entra en otro editor y una identidad distinta no puede adoptarse', async () => {
  const identity = 'abcdabcdabcd4bcd8bcdabcdabcdabcd'
  const current = { ...finding, finding_id: identity }
  let finish
  const view = await mountDecision({ getFindings: async () => [current], saveFinding: async () => { throw new Error('Conflicto') },
    getFinding: () => new Promise(resolve => { finish = resolve }) })
  try {
    await clickText(view.root, 'Hallazgos'); await clickText(view.root, 'Editar'); await clickText(view.root, 'Guardar Ficha')
    await clickText(view.root, 'Ver ficha actual sin reemplazar borrador')
    await clickText(view.root, 'Cancelar'); await clickText(view.root, 'Editar')
    finish({ ...current, body: 'Respuesta anterior' }); await flush()
    assert.equal(view.root.querySelector('[data-testid="finding-current-version"]'), null)
    await clickText(view.root, 'Guardar Ficha'); await clickText(view.root, 'Ver ficha actual sin reemplazar borrador')
    finish({ ...current, finding_id: 'bbbbbbbbbbbb4bbb8bbbbbbbbbbbbbbb' }); await flush()
    assert.equal(view.root.querySelector('[data-testid="finding-current-version"]'), null)
    assert.match(view.root.querySelector('[data-testid="finding-save-error"]').textContent, /identidad o metadatos/)
  } finally { view.cleanup() }
})

test('lista tardía del proyecto anterior no ofrece fichas para editar en el actual', async () => {
  const route = reactive({ params: { id: 'fixture', type: 'engagement' } })
  let finish
  const view = await mountDecision({ getFindings: id => id === 'fixture' ? new Promise(resolve => { finish = resolve }) : Promise.resolve([]) }, route)
  try {
    await clickText(view.root, 'Hallazgos'); route.params.id = 'other'; await flush()
    finish([finding]); await flush()
    assert.equal(view.root.querySelector('[data-testid="finding-identity"]'), null)
  } finally { view.cleanup() }
})

test('borrado obsoleto conserva ficha y recarga exige otra confirmación con versión actual', async () => {
  const calls = [], confirmations = []
  const previous = globalThis.confirm
  globalThis.confirm = message => { confirmations.push(message); return true }
  let fresh = false
  const latest = { ...finding, source_sha256: 'e'.repeat(64), frontmatter: { ...finding.frontmatter, title: 'Actual' } }
  const view = await mountDecision({ getFindings: async () => [fresh ? latest : finding],
    deleteFinding: async (...args) => { calls.push(args); if (calls.length === 1) throw new Error('La ficha cambió; no se eliminó.') } })
  try {
    await clickText(view.root, 'Hallazgos'); await clickText(view.root, 'Eliminar')
    assert.deepEqual(calls[0], ['fixture', 'legacy', 'engagement', finding.source_sha256])
    assert.match(view.root.querySelector('[data-testid="finding-delete-error"]').textContent, /no se eliminó/)
    assert.equal(confirmations.length, 1)
    fresh = true; await clickText(view.root, 'Recargar fichas para revisar')
    assert.match(view.root.textContent, /Actual/); assert.equal(calls.length, 1)
    await clickText(view.root, 'Eliminar')
    assert.equal(confirmations.length, 2); assert.equal(calls[1][3], latest.source_sha256)
  } finally { view.cleanup(); globalThis.confirm = previous }
})

test('borrado sin versión o confirmación no envía DELETE', async () => {
  const previous = globalThis.confirm
  globalThis.confirm = () => false
  let calls = 0, missing = false
  const route = reactive({ params: { id: 'fixture', type: 'engagement' } })
  const view = await mountDecision({ getFindings: async () => [{ ...finding, source_sha256: missing ? null : finding.source_sha256 }], deleteFinding: async () => { calls++ } }, route)
  try {
    await clickText(view.root, 'Hallazgos'); await clickText(view.root, 'Eliminar'); assert.equal(calls, 0)
    missing = true
    globalThis.confirm = () => true
    route.params.id = 'other'; await flush(); await clickText(view.root, 'Eliminar')
    assert.equal(calls, 0); assert.match(view.root.querySelector('[data-testid="finding-delete-error"]').textContent, /Falta la versión/)
  } finally { view.cleanup(); globalThis.confirm = previous }
})

for (const failure of [false, true]) test(`borrado pendiente evita duplicados y descarta ${failure ? 'error' : 'éxito'} de otro proyecto`, async () => {
  const previous = globalThis.confirm
  globalThis.confirm = () => true
  const route = reactive({ params: { id: 'fixture', type: 'engagement' } })
  let finish, calls = 0
  const view = await mountDecision({ getFindings: async () => [finding], deleteFinding: () => { calls++; return new Promise((resolve,reject) => { finish = failure ? reject : resolve }) } }, route)
  try {
    await clickText(view.root, 'Hallazgos'); await clickText(view.root, 'Eliminar'); await clickText(view.root, 'Eliminando')
    assert.equal(calls, 1)
    route.params.id = 'other'; await flush()
    finish(new Error('Fallo anterior')); await flush()
    assert.equal(view.root.querySelector('[data-testid="finding-delete-error"]'), null)
    assert.match(view.root.textContent, /Eliminar/)
  } finally { view.cleanup(); globalThis.confirm = previous }
})

test('fuente inválida se conserva visible sin candidato ni editor/borrado y abre el original', async () => {
  let writes = 0, previews = []
  const source = { ...finding, source_error: 'Metadata inválida o ambigua.', body: '---\ntitle: [\n---\n<script>hostile()</script>',
    frontmatter: { title: 'legacy.md', status: 'BLOCKED', severity: 'UNKNOWN' }, finding_id: null, artifact_refs: [] }
  const view = await mountDecision({ getFindings: async () => [source], saveFinding: async () => { writes++ }, deleteFinding: async () => { writes++ },
    getArtifactContent: async (...args) => { previews.push(args); return { content: source.body, sha256: source.source_sha256, preview_kind: 'text', truncated: false } } })
  try {
    await clickText(view.root, 'Hallazgos')
    assert.match(view.root.querySelector('[data-testid="finding-source-error"]').textContent, /Metadata inválida/)
    assert.doesNotMatch(view.root.textContent, /CANDIDATE|se asignará al guardar/)
    await clickText(view.root, 'Editar'); assert.equal(view.root.querySelector('[data-testid="finding-markdown"]'), null)
    const remove = [...view.root.querySelectorAll('button')].find(b => b.textContent.trim() === 'Eliminar')
    assert.equal(remove.disabled, true); remove.click(); await flush(); assert.equal(writes, 0)
    assert.equal(view.root.querySelector('script'), null)
    await clickText(view.root, 'Revisar fuente original')
    assert.equal(previews.length, 1)
    assert.equal(previews[0][1], 'evidence/legacy.md')
  } finally { view.cleanup() }
})

test('comparación con metadata inválida no se adopta ni reemplaza borrador', async () => {
  const view = await mountDecision({ getFindings: async () => [finding], saveFinding: async () => { throw new Error('Conflicto') },
    getFinding: async () => ({ ...finding, source_error: 'Metadata inválida', body: 'Invalid source' }) })
  try {
    await clickText(view.root, 'Hallazgos'); await clickText(view.root, 'Editar'); await clickText(view.root, 'Guardar Ficha')
    await clickText(view.root, 'Ver ficha actual sin reemplazar borrador')
    assert.equal(view.root.querySelector('[data-testid="finding-current-version"]'), null)
    assert.equal(view.root.querySelector('[data-testid="finding-markdown"]').value, body)
    assert.match(view.root.querySelector('[data-testid="finding-save-error"]').textContent, /identidad o metadatos/)
  } finally { view.cleanup() }
})

test('reparación externa y recarga quitan error de fuente y habilitan edición', async () => {
  let repaired = false
  const view = await mountDecision({ getFindings: async () => [repaired ? finding : { ...finding, source_error: 'Fuente inválida' }] })
  try {
    await clickText(view.root, 'Hallazgos'); repaired = true
    await clickText(view.root, 'Recargar fichas tras revisar')
    assert.equal(view.root.querySelector('[data-testid="finding-source-error"]'), null)
    await clickText(view.root, 'Editar')
    assert.equal(view.root.querySelector('[data-testid="finding-markdown"]').value, body)
  } finally { view.cleanup() }
})
