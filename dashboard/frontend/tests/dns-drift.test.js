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

async function mount(api, route = { params: { id: 'test-scope-proj', type: 'engagement' } }) {
  globalThis.fixtureDnsRoute = route
  globalThis.fixtureDnsApi = new Proxy(api, {
    get: (target, key) => target[key] || (async () => ({})),
  })
  const source = await readFile(new URL('../src/views/EngagementDetailView.vue', import.meta.url), 'utf8')
  const { parse, compileScript } = await import('@vue/compiler-sfc')
  const { descriptor } = parse(source)
  let code = compileScript(descriptor, { id: 'engagement-dns-drift', inlineTemplate: true }).content
    .replace(/from ["']vue["']/g, `from ${JSON.stringify(vueUrl)}`)
    .replace("import { useRoute, useRouter } from 'vue-router'", "const useRoute = () => globalThis.fixtureDnsRoute; const useRouter = () => ({ push() {} })")
    .replace("import { api } from '../api'", 'const api = globalThis.fixtureDnsApi')
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
  return {
    root,
    cleanup() {
      app.unmount()
      root.remove()
    },
  }
}

test('tarjeta de deriva DNS permite verificar resolución dinámica y muestra alertas en pestaña alcance (V3-01i)', async () => {
  let calledDnsDrift = false
  const fakeDnsResult = {
    timestamp: '2026-10-12T19:00:00Z',
    status: 'WARNING',
    domains_count: 1,
    violations_count: 0,
    drift_count: 1,
    results: [
      {
        domain: 'api.target.local',
        resolved_ips: ['10.0.0.5'],
        known_ips: ['192.168.1.10'],
        status: 'DRIFT_WITHIN_SCOPE',
        is_in_scope: true,
        has_drift: true,
        added_ips: ['10.0.0.5'],
        removed_ips: ['192.168.1.10'],
        out_of_scope_ips: [],
      },
    ],
  }

  const mockApi = {
    getEngagementDetail: async () => ({
      name: 'Scope Test Project',
      type: 'engagement',
      created_at: '2026-10-11T10:00:00Z',
      stats: { findings: 0, creds: 0, artifacts: 0 },
    }),
    getScope: async () => ({
      engagement: { id: 'test-scope-proj' },
      authorization: { allow_passive: true, allow_active: false, reference: 'Test' },
      scope: {
        in_scope: { domains: ['api.target.local'] },
        out_of_scope: {},
      },
      operational_limits: { max_requests_per_second: 5 },
    }),
    getFindings: async () => [],
    getLoot: async () => ({ credentials: [] }),
    getArtifacts: async () => [],
    getReconStatus: async () => ({ running: false }),
    getScopeBoundaries: async () => ({
      enforcement_points: [],
      unintercepted_vectors: [],
      active_scope_guard: true,
    }),
    getDnsDrift: async (id) => {
      calledDnsDrift = true
      return fakeDnsResult
    },
  }

  const { root, cleanup } = await mount(mockApi)

  try {
    // Cambiar a pestaña de Alcance
    const scopeTabBtn = [...root.querySelectorAll('button')].find(b => b.textContent.includes('Alcance'))
    assert.ok(scopeTabBtn, 'Debe existir botón de pestaña Alcance')
    scopeTabBtn.click()
    await flush()

    // Comprobar que existe la tarjeta de deriva DNS
    const driftCard = root.querySelector('[data-testid="scope-dns-drift-card"]')
    assert.ok(driftCard, 'Debe existir la tarjeta scope-dns-drift-card')

    // Pulsar botón de verificar deriva DNS
    const checkBtn = root.querySelector('[data-testid="check-dns-drift-btn"]')
    assert.ok(checkBtn, 'Debe existir el botón check-dns-drift-btn')
    checkBtn.click()
    await flush()

    assert.ok(calledDnsDrift, 'getDnsDrift debe ser invocado al pulsar el botón')

    // Comprobar insignia de estado
    const badge = root.querySelector('[data-testid="dns-drift-status-badge"]')
    assert.ok(badge, 'Debe mostrarse badge de estado')
    assert.match(badge.textContent, /DERIVA DETECTADA/)

    // Comprobar fila de dominio
    const row = root.querySelector('[data-testid="domain-drift-row"]')
    assert.ok(row, 'Debe renderizarse domain-drift-row')
    assert.ok(row.textContent.includes('api.target.local'))
    assert.ok(row.textContent.includes('DRIFT_WITHIN_SCOPE'))
    assert.ok(row.textContent.includes('+10.0.0.5'))
  } finally {
    cleanup()
  }
})
