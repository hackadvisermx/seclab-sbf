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

async function mount(api, route = { params: { id: 'test-metrics-proj', type: 'engagement' } }) {
  globalThis.fixtureMetricsRoute = route
  globalThis.fixtureMetricsApi = new Proxy(api, {
    get: (target, key) => target[key] || (async () => ({})),
  })
  const source = await readFile(new URL('../src/views/EngagementDetailView.vue', import.meta.url), 'utf8')
  const { parse, compileScript } = await import('@vue/compiler-sfc')
  const { descriptor } = parse(source)
  let code = compileScript(descriptor, { id: 'engagement-metrics-history', inlineTemplate: true }).content
    .replace(/from ["']vue["']/g, `from ${JSON.stringify(vueUrl)}`)
    .replace("import { useRoute, useRouter } from 'vue-router'", "const useRoute = () => globalThis.fixtureMetricsRoute; const useRouter = () => ({ push() {} })")
    .replace("import { api } from '../api'", 'const api = globalThis.fixtureMetricsApi')
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

test('sección de historial de métricas renderiza snapshots, deltas y permite capturar nueva instantánea (V3-07e)', async () => {
  let capturedSnapshot = false
  const fakeHistory = [
    {
      snapshot_id: 'snap1234',
      timestamp: '2026-10-12T19:00:00Z',
      audit_readiness_score: 75.0,
      delta_score: 25.0,
      author: 'tester',
      pillars: {
        scope: { score: 100 },
        recon: { score: 100 },
        findings: { score: 50 },
        deliverables: { score: 50 },
      },
    },
    {
      snapshot_id: 'snap0001',
      timestamp: '2026-10-12T18:00:00Z',
      audit_readiness_score: 50.0,
      delta_score: 0.0,
      author: 'tester',
      pillars: {
        scope: { score: 100 },
        recon: { score: 50 },
        findings: { score: 25 },
        deliverables: { score: 25 },
      },
    },
  ]

  const mockApi = {
    getEngagementDetail: async () => ({
      name: 'Metrics Test Project',
      type: 'engagement',
      created_at: '2026-10-11T10:00:00Z',
      stats: { findings: 1, creds: 0, artifacts: 1 },
    }),
    getScope: async () => ({
      engagement: { id: 'test-metrics-proj' },
      authorization: { allow_passive: true, allow_active: false, reference: 'Test' },
      scope: { in_scope: { domains: ['target.local'] } },
    }),
    getFindings: async () => [],
    getLoot: async () => ({ credentials: [] }),
    getArtifacts: async () => [],
    getReconStatus: async () => ({ running: false }),
    getMetrics: async () => ({
      audit_readiness_score: 75.0,
      is_fully_audited: false,
      pillars: {
        scope: { status: 'COMPLETE', score: 100 },
        recon: { status: 'COMPLETE', score: 100 },
        findings: { status: 'IN_PROGRESS', score: 50 },
        deliverables: { status: 'IN_PROGRESS', score: 50 },
      },
      findings: { total_findings: 1, provenance_coverage_pct: 100 },
      recon: { completed_jobs: 1 },
      report: { has_report: false, has_deliverables: false },
    }),
    getMetricsHistory: async () => fakeHistory,
    recordMetricsSnapshot: async () => {
      capturedSnapshot = true
      return { snapshot_id: 'snapNew99', audit_readiness_score: 75.0 }
    },
  }

  const { root, cleanup } = await mount(mockApi)

  try {
    // Cambiar a pestaña Métricas
    const metricsTabBtn = [...root.querySelectorAll('button')].find(b => b.textContent.includes('Métricas'))
    assert.ok(metricsTabBtn, 'Debe existir botón de pestaña Métricas')
    metricsTabBtn.click()
    await flush()

    // Comprobar que existe la sección de historial de métricas
    const historySection = root.querySelector('[data-testid="metrics-history-section"]')
    assert.ok(historySection, 'Debe existir metrics-history-section')

    // Comprobar items de historial
    const items = root.querySelectorAll('[data-testid="metrics-history-item"]')
    assert.equal(items.length, 2, 'Deben renderizarse los 2 snapshots históricos')
    assert.ok(items[0].textContent.includes('#snap1234'))
    assert.ok(items[0].textContent.includes('75 / 100'))

    // Comprobar delta score
    const deltas = root.querySelectorAll('[data-testid="metrics-history-delta"]')
    assert.ok(deltas[0].textContent.includes('+25%'))

    // Pulsar botón de capturar snapshot
    const snapBtn = root.querySelector('[data-testid="record-metrics-snapshot-btn"]')
    assert.ok(snapBtn, 'Debe existir el botón record-metrics-snapshot-btn')
    snapBtn.click()
    await flush()

    assert.equal(capturedSnapshot, true, 'api.recordMetricsSnapshot debe ser llamado al hacer clic')
  } finally {
    cleanup()
  }
})
