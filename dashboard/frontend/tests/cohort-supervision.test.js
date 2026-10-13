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

async function mount(api, route = { params: { id: 'test-cohort-proj', type: 'engagement' } }) {
  globalThis.fixtureCohortRoute = route
  globalThis.fixtureCohortApi = new Proxy(api, {
    get: (target, key) => target[key] || (async () => ({})),
  })
  const source = await readFile(new URL('../src/views/EngagementDetailView.vue', import.meta.url), 'utf8')
  const { parse, compileScript } = await import('@vue/compiler-sfc')
  const { descriptor } = parse(source)
  let code = compileScript(descriptor, { id: 'engagement-cohort-supervision', inlineTemplate: true }).content
    .replace(/from ["']vue["']/g, `from ${JSON.stringify(vueUrl)}`)
    .replace("import { useRoute, useRouter } from 'vue-router'", "const useRoute = () => globalThis.fixtureCohortRoute; const useRouter = () => ({ push() {} })")
    .replace("import { api } from '../api'", 'const api = globalThis.fixtureCohortApi')
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

test('tarjeta de supervisión de cohorte docente renderiza tasa de aula y proyectos (V3-06e)', async () => {
  let calledCohort = false
  const fakeCohortSummary = {
    total_cohort_projects: 3,
    cohort_total_checkpoints: 12,
    cohort_passed_checkpoints: 9,
    cohort_completion_pct: 75.0,
    blocked_projects_count: 1,
    fully_completed_projects_count: 1,
    projects: [
      { id: 'alumno_alpha', type: 'engagement', overall_status: 'PASS', passed_count: 4, is_blocked: false },
      { id: 'alumno_beta', type: 'reto', overall_status: 'WARNING', passed_count: 3, is_blocked: false },
      { id: 'alumno_gamma', type: 'engagement', overall_status: 'BLOCKED', passed_count: 2, is_blocked: true },
    ],
  }

  const mockApi = {
    getEngagementDetail: async () => ({
      name: 'Cohort Test Project',
      type: 'engagement',
      created_at: '2026-10-11T10:00:00Z',
      stats: { findings: 0, creds: 0, artifacts: 0 },
    }),
    getScope: async () => ({
      engagement: { id: 'test-cohort-proj' },
      authorization: { allow_passive: true, allow_active: false, reference: 'Test' },
      scope: { in_scope: { domains: ['target.local'] } },
    }),
    getFindings: async () => [],
    getLoot: async () => ({ credentials: [] }),
    getArtifacts: async () => [],
    getReconStatus: async () => ({ running: false }),
    getSupervision: async () => ({
      overall_status: 'PASS',
      checkpoints: [
        { id: 'cp_scope', title: 'Alcance', stage: 'scope', status: 'PASSED', reason: 'OK' },
        { id: 'cp_recon', title: 'Recon', stage: 'recon', status: 'PASSED', reason: 'OK' },
        { id: 'cp_evidence', title: 'Evidencia', stage: 'triage', status: 'PASSED', reason: 'OK' },
        { id: 'cp_report', title: 'Reporte', stage: 'reporting', status: 'PASSED', reason: 'OK' },
      ],
      pending_actions: [],
    }),
    getCohortSupervisionSummary: async () => {
      calledCohort = true
      return fakeCohortSummary
    },
  }

  const { root, cleanup } = await mount(mockApi)

  try {
    // Cambiar a pestaña Supervisión
    const supTabBtn = [...root.querySelectorAll('button')].find(b => b.textContent.includes('Supervisión'))
    assert.ok(supTabBtn, 'Debe existir botón de pestaña Supervisión')
    supTabBtn.click()
    await flush()

    // Comprobar que existe la tarjeta de cohorte docente
    const cohortCard = root.querySelector('[data-testid="cohort-supervision-overview-card"]')
    assert.ok(cohortCard, 'Debe existir cohort-supervision-overview-card')

    // Pulsar botón de actualizar cohorte
    const refreshBtn = root.querySelector('[data-testid="refresh-cohort-supervision-btn"]')
    assert.ok(refreshBtn, 'Debe existir el botón refresh-cohort-supervision-btn')
    refreshBtn.click()
    await flush()

    assert.equal(calledCohort, true, 'getCohortSupervisionSummary debe ser invocado')

    // Comprobar porcentaje de cumplimiento de aula
    const pctBadge = root.querySelector('[data-testid="cohort-completion-pct"]')
    assert.ok(pctBadge, 'Debe mostrarse badge de porcentaje de cohorte')
    assert.match(pctBadge.textContent, /75(\.0)?%/)

    // Comprobar proyectos listados
    const rows = root.querySelectorAll('[data-testid="cohort-project-row"]')
    assert.equal(rows.length, 3, 'Deben renderizarse los 3 proyectos de la cohorte')
    assert.ok(rows[0].textContent.includes('alumno_alpha'))
    assert.ok(rows[1].textContent.includes('alumno_beta'))
    assert.ok(rows[2].textContent.includes('alumno_gamma'))
    assert.ok(rows[2].textContent.includes('BLOQUEADO'))
  } finally {
    cleanup()
  }
})
