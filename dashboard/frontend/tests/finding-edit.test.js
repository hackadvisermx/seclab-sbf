import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { createRequire } from 'node:module'
import { pathToFileURL } from 'node:url'
import { test } from 'node:test'
import { JSDOM } from 'jsdom'
const browser = new JSDOM('<body></body>', { url: 'http://localhost' })
for (const key of ['window','document','Element','SVGElement','HTMLElement','Node','localStorage']) globalThis[key] = browser.window[key]
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
  for (const name of ['report-security','scope-utils','recon-results']) code = code.replace(`from '../${name}'`, `from ${JSON.stringify(new URL(`../src/${name}.js`, import.meta.url).href)}`)
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
