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

async function mount(api, route = { params: { id: 'test-proj', type: 'engagement' } }) {
  globalThis.fixtureMetricsRoute = route
  globalThis.fixtureMetricsApi = new Proxy(api, {
    get: (target, key) => target[key] || (async () => ({}))
  })
  const source = await readFile(new URL('../src/views/EngagementDetailView.vue', import.meta.url), 'utf8')
  const { parse, compileScript } = await import('@vue/compiler-sfc')
  const { descriptor } = parse(source)
  let code = compileScript(descriptor, { id: 'engagement-metrics', inlineTemplate: true }).content
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
  return { root, cleanup() { app.unmount(); root.remove() } }
}

async function clickText(root, text) {
  const button = [...root.querySelectorAll('button')].find(b => b.textContent.trim().includes(text))
  assert.ok(button, `Missing button containing "${text}"`)
  button.click()
  await flush()
}

const mockMetricsData = {
  engagement_id: 'test-proj',
  audit_readiness_score: 75,
  is_fully_audited: false,
  scope: {
    has_scope: true,
    allow_passive: true,
    allow_active: true,
    domains_count: 2,
    ips_count: 1,
    exclusions_count: 1,
    out_of_scope_actions_executed: 0
  },
  recon: {
    has_recon_database: true,
    total_jobs: 3,
    completed_jobs: 3,
    failed_jobs: 0,
    blocked_jobs: 0,
    stages_executed_count: 2,
    stages_executed: ['subdomains', 'probing']
  },
  findings: {
    total_findings: 5,
    confirmed_count: 3,
    candidate_count: 1,
    disproved_count: 1,
    findings_with_provenance: 4,
    provenance_coverage_pct: 80.0,
    severity_breakdown: {
      critical: 1,
      high: 2,
      medium: 1,
      low: 1,
      info: 0
    }
  },
  report: {
    has_report: true,
    report_size_bytes: 2048,
    has_deliverables: true,
    has_artifact_manifest: true,
    manifest_artifacts_count: 8
  }
}

test('pestaña de métricas operacionales renderiza score de madurez, procedencia y 4 tarjetas', async () => {
  let calledGetMetrics = false

  const api = {
    getEngagementDetail: async () => ({
      name: 'Test Project',
      type: 'engagement',
      created_at: '2026-10-11T10:00:00Z',
      stats: { findings: 5, creds: 0, artifacts: 8 }
    }),
    getScope: async () => ({ target: 'example.com', authorization: { allow_passive: true, allow_active: true } }),
    getFindings: async () => [],
    getLoot: async () => ({ credentials: [] }),
    getArtifacts: async () => [],
    getReconStatus: async () => ({ running: false }),
    getMetrics: async (id) => {
      calledGetMetrics = true
      assert.equal(id, 'test-proj')
      return mockMetricsData
    }
  }

  const { root, cleanup } = await mount(api)

  try {
    // 1. Clic en pestaña Métricas de Auditoría
    await clickText(root, 'Métricas de Auditoría')
    assert.equal(calledGetMetrics, true, 'Debe invocar api.getMetrics al abrir la pestaña')

    // 2. Verificar vista presente
    const metricsView = root.querySelector('[data-testid="engagement-metrics-view"]')
    assert.ok(metricsView, 'La vista de métricas debe estar presente en el DOM')

    // 3. Verificar score de madurez
    const scoreBadge = root.querySelector('[data-testid="audit-readiness-score"]')
    assert.ok(scoreBadge, 'Insignia de madurez debe existir')
    assert.match(scoreBadge.textContent, /75 \/ 100/)

    // 4. Verificar tarjeta de Alcance
    const scopeCard = root.querySelector('[data-testid="metrics-card-scope"]')
    assert.ok(scopeCard, 'Tarjeta de alcance debe existir')
    assert.match(scopeCard.textContent, /target\.yaml Activo/)
    assert.match(scopeCard.textContent, /0 violaciones/)

    // 5. Verificar tarjeta de Reconocimiento
    const reconCard = root.querySelector('[data-testid="metrics-card-recon"]')
    assert.ok(reconCard, 'Tarjeta de recon debe existir')
    assert.match(reconCard.textContent, /recon_jobs\.db/)
    assert.match(reconCard.textContent, /subdomains, probing/)

    // 6. Verificar tarjeta de Hallazgos y procedencia
    const findingsCard = root.querySelector('[data-testid="metrics-card-findings"]')
    assert.ok(findingsCard, 'Tarjeta de hallazgos debe existir')
    const provPct = root.querySelector('[data-testid="provenance-coverage-pct"]')
    assert.ok(provPct, 'Insignia de cobertura de procedencia debe existir')
    assert.match(provPct.textContent, /80%/)
    assert.match(findingsCard.textContent, /Crit: 1/)
    assert.match(findingsCard.textContent, /High: 2/)

    // 7. Verificar tarjeta de Reporte y entregables
    const reportCard = root.querySelector('[data-testid="metrics-card-report"]')
    assert.ok(reportCard, 'Tarjeta de reporte debe existir')
    assert.match(reportCard.textContent, /REPORT\.md/)
    assert.match(reportCard.textContent, /Disponibles/)
    assert.match(reportCard.textContent, /8/)
  } finally {
    cleanup()
  }
})
