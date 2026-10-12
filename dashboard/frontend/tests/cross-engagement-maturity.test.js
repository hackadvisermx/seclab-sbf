import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { createRequire } from 'node:module'
import { pathToFileURL } from 'node:url'
import { test } from 'node:test'
import { JSDOM } from 'jsdom'

const browser = new JSDOM('<body></body>', { url: 'http://localhost' })
for (const name of ['window', 'document', 'Element', 'SVGElement', 'HTMLElement', 'Node', 'history', 'location']) {
  globalThis[name] = browser.window[name]
}

const { createApp } = await import('vue')
const { createRouter, createMemoryHistory } = await import('vue-router')
const require = createRequire(import.meta.url)
const vueUrl = pathToFileURL(require.resolve('vue/dist/vue.runtime.esm-bundler.js')).href
const vueRouterUrl = import.meta.resolve('vue-router')

async function mountView(filename, apiMock) {
  globalThis.fixtureMetricsApi = apiMock
  const source = await readFile(new URL(`../src/${filename}`, import.meta.url), 'utf8')
  const { parse, compileScript } = await import('@vue/compiler-sfc')
  const { descriptor } = parse(source)
  const compiled = compileScript(descriptor, { id: filename, inlineTemplate: true })
  const code = compiled.content
    .replace(/from ["']vue["']/g, `from ${JSON.stringify(vueUrl)}`)
    .replace(/from ["']vue-router["']/g, `from ${JSON.stringify(vueRouterUrl)}`)
    .replace("import { api } from '../api'", 'const api = globalThis.fixtureMetricsApi')
    .replace(
      /import DeleteProjectButton from ['"]\.\.\/components\/DeleteProjectButton\.vue['"]/,
      'const DeleteProjectButton = { props: ["projectId", "projectType"], emits: ["deleted"], template: "<button type=\\"button\\">Eliminar</button>" }'
    )
  const component = (await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}#${Math.random()}`)).default

  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/engagements', component: { template: '<div />' } },
      { path: '/engagements/:type/:id', component: { template: '<div id="detail-stub">detalle</div>' } },
    ],
  })
  await router.push('/engagements')
  await router.isReady()

  const root = document.createElement('div')
  document.body.append(root)
  const app = createApp(component)
  app.use(router)
  app.component('router-link', { props: ['to'], template: '<a :href="to"><slot /></a>' })
  app.mount(root)
  await new Promise(r => setTimeout(r, 60))
  return {
    root,
    cleanup() {
      app.unmount()
      root.remove()
    },
  }
}

test('EngagementsView renderiza tarjeta de resumen de madurez global cruzada (V3-07d)', async () => {
  const fakeSummary = {
    total_projects: 4,
    total_engagements: 3,
    total_retos: 1,
    avg_readiness_score: 75.5,
    fully_audited_count: 2,
    total_findings: 8,
    confirmed_findings_count: 5,
    candidate_findings_count: 3,
    findings_by_severity: { critical: 2, high: 3, medium: 2, low: 1, info: 0 },
    total_findings_with_provenance: 6,
    overall_provenance_coverage_pct: 75.0,
    total_recon_jobs: 12,
    total_completed_jobs: 10,
    projects: [],
  }

  const apiMock = {
    getEngagements: async () => [
      { id: 'eng-1', name: 'Alpha', type: 'engagement', client_or_platform: 'Client X' },
    ],
    getCrossEngagementMetricsSummary: async () => fakeSummary,
  }

  const { root, cleanup } = await mountView('views/EngagementsView.vue', apiMock)
  try {
    const card = root.querySelector('[data-testid="cross-engagement-maturity-card"]')
    assert.ok(card, 'La tarjeta de madurez global debe estar visible en el DOM')

    const scoreEl = root.querySelector('[data-testid="avg-readiness-score"]')
    assert.ok(scoreEl, 'El score promedio de madurez debe estar presente')
    assert.match(scoreEl.textContent, /75\.5%/)

    const projectsEl = root.querySelector('[data-testid="total-projects-count"]')
    assert.ok(projectsEl, 'El contador total de proyectos debe estar presente')
    assert.match(projectsEl.textContent, /4/)

    const findingsEl = root.querySelector('[data-testid="total-findings-count"]')
    assert.ok(findingsEl, 'El contador total de hallazgos debe estar presente')
    assert.match(findingsEl.textContent, /8/)

    const provEl = root.querySelector('[data-testid="overall-provenance-pct"]')
    assert.ok(provEl, 'El porcentaje de cobertura de procedencia debe estar presente')
    assert.match(provEl.textContent, /75%/)

    const jobsEl = root.querySelector('[data-testid="total-recon-jobs"]')
    assert.ok(jobsEl, 'El contador total de recon jobs debe estar presente')
    assert.match(jobsEl.textContent, /12/)
  } finally {
    cleanup()
  }
})
