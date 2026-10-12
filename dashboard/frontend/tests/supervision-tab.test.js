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
  globalThis.fixtureSupervisionRoute = route
  globalThis.fixtureSupervisionApi = new Proxy(api, {
    get: (target, key) => target[key] || (async () => ({}))
  })
  const source = await readFile(new URL('../src/views/EngagementDetailView.vue', import.meta.url), 'utf8')
  const { parse, compileScript } = await import('@vue/compiler-sfc')
  const { descriptor } = parse(source)
  let code = compileScript(descriptor, { id: 'engagement-supervision', inlineTemplate: true }).content
    .replace(/from ["']vue["']/g, `from ${JSON.stringify(vueUrl)}`)
    .replace("import { useRoute, useRouter } from 'vue-router'", "const useRoute = () => globalThis.fixtureSupervisionRoute; const useRouter = () => ({ push() {} })")
    .replace("import { api } from '../api'", 'const api = globalThis.fixtureSupervisionApi')
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

const mockSupervisionData = {
  engagement_id: 'test-proj',
  overall_status: 'WARNING',
  checkpoints: [
    {
      id: 'cp_scope',
      name: 'Alcance Autorizado (target.yaml)',
      status: 'PASS',
      detail: 'Alcance declarado y vigente con autorización explícita.',
      recommendation: 'Mantener vigencia del alcance.'
    },
    {
      id: 'cp_recon',
      name: 'Reconocimiento y Huellas',
      status: 'WARNING',
      detail: '1 jobs registrados, pero la última etapa falló o no terminó limpia.',
      recommendation: 'Reanudar o revisar recon_jobs.db.'
    },
    {
      id: 'cp_evidence',
      name: 'Evidencia y Trazabilidad de Hallazgos',
      status: 'PASS',
      detail: '3 hallazgo(s) registrados con evidencia vinculada.',
      recommendation: 'Asegurar procedencia completa.'
    },
    {
      id: 'cp_report',
      name: 'Reporte y Entregables',
      status: 'WARNING',
      detail: 'REPORT.md presente pero sin paquete de entregables.',
      recommendation: 'Compilar y empaquetar entregables.'
    }
  ],
  blocking_issues: [],
  warnings: ['La última etapa de reconocimiento no concluyó con éxito.'],
  pending_actions: ['Generar paquete de entregables con pt-report pack']
}

test('pestaña de supervisión pedagógica renderiza checkpoints formativos y estado global', async () => {
  let calledSupervision = false
  const api = {
    getEngagementDetail: async () => ({
      name: 'Test Project',
      type: 'engagement',
      created_at: '2026-10-11T10:00:00Z',
      stats: { findings: 3, creds: 0, artifacts: 1 }
    }),
    getScope: async () => ({ target: 'example.com', authorization: { allow_passive: true } }),
    getFindings: async () => [],
    getLoot: async () => ({ credentials: [] }),
    getArtifacts: async () => [],
    getReconStatus: async () => ({ running: false }),
    getSupervision: async (id) => {
      calledSupervision = true
      assert.equal(id, 'test-proj')
      return mockSupervisionData
    }
  }

  const { root, cleanup } = await mount(api)

  try {
    // 1. Clic en la pestaña de Supervisión Pedagógica
    await clickText(root, 'Supervisión Pedagógica')
    assert.equal(calledSupervision, true, 'api.getSupervision debe ser invocado al abrir la pestaña')

    // 2. Verificar que la vista de supervisión se muestra
    const supervisionView = root.querySelector('[data-testid="engagement-supervision-view"]')
    assert.ok(supervisionView, 'La vista de supervisión debe estar presente en el DOM')

    // 3. Verificar estado global
    const overallBadge = root.querySelector('[data-testid="supervision-overall-status"]')
    assert.ok(overallBadge, 'Badge de estado general debe existir')
    assert.match(overallBadge.textContent, /WARNING/)

    // 4. Verificar checkpoints
    for (const cp of mockSupervisionData.checkpoints) {
      const cpCard = root.querySelector(`[data-testid="checkpoint-${cp.id}"]`)
      assert.ok(cpCard, `Checkpoint ${cp.id} debe mostrarse`)
      assert.ok(cpCard.textContent.includes(cp.name), `Debe contener nombre: ${cp.name}`)
      assert.ok(cpCard.textContent.includes(cp.status), `Debe contener status: ${cp.status}`)
      assert.ok(cpCard.textContent.includes(cp.detail), `Debe contener detail: ${cp.detail}`)
    }

    // 5. Verificar advertencias formativas
    assert.match(supervisionView.textContent, /La última etapa de reconocimiento no concluyó con éxito/)

    // 6. Verificar acciones pendientes
    assert.match(supervisionView.textContent, /Generar paquete de entregables con pt-report pack/)
  } finally {
    cleanup()
  }
})
