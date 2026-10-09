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
const finding = { slug: 'legacy', filename: 'legacy.md', frontmatter: { title: 'Original', severity: 'INFO', status: 'PROVEN', asset: 'example.test', cvss_score: 0, cvss_vector: 'CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:N' }, artifact_refs: [{ path: 'recon/valid.txt', sha256: 'c'.repeat(64) }], verification_rationale: 'Operador reviso el fixture', body }
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
    assert.match(rows[1].textContent, /URLs: 5/)
    assert.match(rows[1].textContent, /artefactos previos; no acreditan resultados nuevos/)
    assert.match(rows[2].textContent, /simulación no genera resultados/)
    assert.match(rows[3].textContent, /Sin resumen de resultados conservado/)
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
