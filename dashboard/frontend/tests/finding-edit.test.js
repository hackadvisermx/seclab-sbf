import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { createRequire } from 'node:module'
import { pathToFileURL } from 'node:url'
import { test } from 'node:test'
import { JSDOM } from 'jsdom'
const browser = new JSDOM('<body></body>', { url: 'http://localhost' })
for (const key of ['window','document','Document','Element','SVGElement','HTMLElement','Node','localStorage']) globalThis[key] = browser.window[key]
const { createApp, nextTick } = await import('vue')
const require = createRequire(import.meta.url)
const vueUrl = pathToFileURL(require.resolve('vue/dist/vue.runtime.esm-bundler.js')).href
const body = '## Descripción\nOriginal\n\n## Control negativo\nPrueba personalizada\n\n```http\nGET / HTTP/1.1\n```'
const finding = { slug: 'legacy', filename: 'legacy.md', frontmatter: { title: 'Original', severity: 'INFO', status: 'PROVEN', cvss_score: 0, cvss_vector: 'CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:N' }, body }
async function flush() { await nextTick(); await new Promise(r => setTimeout(r, 0)); await nextTick() }
async function mount(api) {
  globalThis.fixtureFindingApi = new Proxy(api, { get: (target, key) => target[key] || (async () => ({})) })
  const source = await readFile(new URL('../src/views/EngagementDetailView.vue', import.meta.url), 'utf8')
  const { parse, compileScript } = await import('@vue/compiler-sfc')
  const { descriptor } = parse(source)
  let code = compileScript(descriptor, { id: 'finding-edit', inlineTemplate: true }).content
    .replace(/from ["']vue["']/g, `from ${JSON.stringify(vueUrl)}`)
    .replace("import { useRoute, useRouter } from 'vue-router'", "const useRoute = () => ({ params: { id: 'fixture', type: 'engagement' } }); const useRouter = () => ({ push() {} })")
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
