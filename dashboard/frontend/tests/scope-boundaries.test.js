import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { createRequire } from 'node:module'
import { pathToFileURL } from 'node:url'
import { test } from 'node:test'
import { JSDOM } from 'jsdom'

const browser = new JSDOM('<body></body>', { url: 'http://localhost' })
for (const key of ['window', 'document', 'Document', 'Element', 'SVGElement', 'HTMLElement', 'Node', 'localStorage']) {
  globalThis[key] = browser.window[key]
}

const { createApp, nextTick } = await import('vue')
const require = createRequire(import.meta.url)
const vueUrl = pathToFileURL(require.resolve('vue/dist/vue.runtime.esm-bundler.js')).href

async function flush() {
  await nextTick()
  await new Promise(r => setTimeout(r, 0))
  await nextTick()
}

async function mountEngagement(api, route = { params: { id: 'test-proj', type: 'engagement' } }) {
  globalThis.fixtureScopeRoute = route
  globalThis.fixtureScopeApi = new Proxy(api, {
    get: (target, key) => target[key] || (async () => ({}))
  })
  const source = await readFile(new URL('../src/views/EngagementDetailView.vue', import.meta.url), 'utf8')
  const { parse, compileScript } = await import('@vue/compiler-sfc')
  const { descriptor } = parse(source)
  let code = compileScript(descriptor, { id: 'engagement-scope', inlineTemplate: true }).content
    .replace(/from ["']vue["']/g, `from ${JSON.stringify(vueUrl)}`)
    .replace("import { useRoute, useRouter } from 'vue-router'", "const useRoute = () => globalThis.fixtureScopeRoute; const useRouter = () => ({ push() {} })")
    .replace("import { api } from '../api'", 'const api = globalThis.fixtureScopeApi')
  for (const name of ['report-security', 'scope-utils', 'recon-results', 'authorization-utils']) {
    code = code.replace(`from '../${name}'`, `from ${JSON.stringify(new URL(`../src/${name}.js`, import.meta.url).href)}`)
  }
  for (const name of ['DeleteProjectButton', 'HelpTooltip']) {
    code = code.replace(new RegExp(`import ${name} from ['"]\\.\\./components/${name}\\.vue['"]`), `const ${name} = { render: () => null }`)
  }
  const component = (await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}#${Math.random()}`)).default
  const root = document.createElement('div')
  document.body.append(root)
  const app = createApp(component)
  app.component('router-link', { template: '<a><slot /></a>' })
  app.mount(root)
  await flush()
  return { root, cleanup() { app.unmount(); root.remove() } }
}

async function mountTerminal() {
  const source = await readFile(new URL('../src/views/TerminalView.vue', import.meta.url), 'utf8')
  const { parse, compileScript } = await import('@vue/compiler-sfc')
  const { descriptor } = parse(source)
  let code = compileScript(descriptor, { id: 'terminal-view', inlineTemplate: true }).content
    .replace(/from ["']vue["']/g, `from ${JSON.stringify(vueUrl)}`)
  const component = (await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}#${Math.random()}`)).default
  const root = document.createElement('div')
  document.body.append(root)
  const app = createApp(component)
  app.mount(root)
  await flush()
  return { root, cleanup() { app.unmount(); root.remove() } }
}

test('pestaña de alcance renderiza tarjeta de fronteras técnicas de Scope Guard', async () => {
  const api = {
    getEngagementDetail: async () => ({
      name: 'Test Project',
      type: 'engagement',
      created_at: '2026-10-11T10:00:00Z',
      stats: { findings: 0, creds: 0, artifacts: 0 }
    }),
    getScope: async () => ({
      target: 'example.com',
      authorization: { allow_passive: true, allow_active: true },
      operational_limits: { max_requests_per_second: 1, max_parallel_threads: 1, dos_testing: false }
    }),
    getFindings: async () => [],
    getLoot: async () => ({ credentials: [] }),
    getArtifacts: async () => [],
    getReconStatus: async () => ({ running: false })
  }

  const { root, cleanup } = await mountEngagement(api)

  try {
    const boundariesCard = root.querySelector('[data-testid="scope-boundaries-card"]')
    assert.ok(boundariesCard, 'La tarjeta de fronteras de Scope Guard debe existir en el DOM')
    assert.match(boundariesCard.textContent, /Frontera Técnica de Scope Guard/)
    assert.match(boundariesCard.textContent, /Interceptado y Validado/)
    assert.match(boundariesCard.textContent, /No Interceptado \(Shell Libre\)/)
    assert.match(boundariesCard.textContent, /Terminal interactiva ttyd/)
  } finally {
    cleanup()
  }
})

test('TerminalView renderiza aviso explícito de límites operacionales de Scope Guard', async () => {
  const { root, cleanup } = await mountTerminal()

  try {
    const notice = root.querySelector('[data-testid="terminal-scope-guard-notice"]')
    assert.ok(notice, 'El aviso de Scope Guard en terminal debe existir en el DOM')
    assert.match(notice.textContent, /Límites Operacionales de Scope Guard/)
    assert.match(notice.textContent, /no son interceptados ni filtrados por el Scope Guard/)
    assert.match(notice.textContent, /operador es el único responsable/)
  } finally {
    cleanup()
  }
})
