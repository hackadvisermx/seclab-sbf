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

async function mountView(apiMock) {
  globalThis.fixtureFindingRoute = { params: { id: 'sample-eng', type: 'engagement' } }
  globalThis.fixtureFindingApi = new Proxy(apiMock, {
    get: (target, key) => target[key] || (async () => ({}))
  })

  const source = await readFile(new URL('../src/views/EngagementDetailView.vue', import.meta.url), 'utf8')
  const { parse, compileScript } = await import('@vue/compiler-sfc')
  const { descriptor } = parse(source)
  let code = compileScript(descriptor, { id: 'audit-next-banner-test', inlineTemplate: true }).content
    .replace(/from ["']vue["']/g, `from ${JSON.stringify(vueUrl)}`)
    .replace("import { useRoute, useRouter } from 'vue-router'", "const useRoute = () => globalThis.fixtureFindingRoute; const useRouter = () => ({ push() {} })")
    .replace("import { api } from '../api'", 'const api = globalThis.fixtureFindingApi')

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

test('franja de siguiente decisión táctica renderiza fase, título y botón de acción', async () => {
  const nextStepFixture = {
    decision_job: { run_id: 'run-123', status: 'blocked', stage: 'probe', dry_run: false },
    next_step: {
      id: 'recon_blocked',
      phase: 'Reconocimiento',
      title: 'Revisar alcance y autorización tras el bloqueo',
      reason: 'Scope Guard bloqueó el último job.',
      command: null,
      ready_for_closure: false,
      action: { view: 'scope', label: 'Revisar alcance y autorización' }
    },
    prompt_available: false,
    prompt: ''
  }

  const view = await mountView({
    getEngagementDetail: async () => ({ id: 'sample-eng', name: 'Sample' }),
    getNextStep: async () => nextStepFixture,
    getScope: async () => ({ scope: { in_scope: { domains: [] } } }),
    getFindings: async () => [],
    getChecklist: async () => ({ matrix: {} }),
    getLoot: async () => ({ credentials: [], files: [] }),
    getReconStatus: async () => ({ summary: {} })
  })

  try {
    const banner = view.root.querySelector('[data-testid="audit-next-banner"]')
    assert.ok(banner, 'El banner de siguiente decisión debe estar presente')
    assert.match(banner.textContent, /Siguiente Decisión/)
    assert.match(banner.textContent, /\[Reconocimiento\]/)
    assert.match(banner.textContent, /Revisar alcance y autorización tras el bloqueo/)

    const actionBtn = banner.querySelector('[data-testid="banner-next-action-btn"]')
    assert.ok(actionBtn, 'Debe existir botón de acción en el banner')
    assert.match(actionBtn.textContent, /Revisar alcance y autorización/)

    // Al hacer clic, navega a la pestaña de alcance
    actionBtn.click()
    await flush()
    assert.match(view.root.textContent, /Reglas de Alcance|target\.yaml/)
  } finally {
    view.cleanup()
  }
})

test('franja de siguiente decisión navega a hallazgos o reporte cuando la recomendación lo indica', async () => {
  const nextStepFixture = {
    next_step: {
      id: 'report_closure',
      phase: 'Reporte',
      title: 'Compilar informe técnico final de auditoría',
      reason: 'Todos los objetivos completados.',
      action: { view: 'report', label: 'Compilar Reporte' }
    }
  }

  const view = await mountView({
    getEngagementDetail: async () => ({ id: 'sample-eng', name: 'Sample' }),
    getNextStep: async () => nextStepFixture,
    getScope: async () => ({ scope: {} }),
    getFindings: async () => [],
    getChecklist: async () => ({ matrix: {} }),
    getLoot: async () => ({ credentials: [], files: [] }),
    getReconStatus: async () => ({ summary: {} }),
    previewReport: async () => ({ title: 'Informe Final', content: '# Final' })
  })

  try {
    const banner = view.root.querySelector('[data-testid="audit-next-banner"]')
    assert.ok(banner)
    assert.match(banner.textContent, /Compilar informe técnico final/)

    const actionBtn = banner.querySelector('[data-testid="banner-next-action-btn"]')
    assert.ok(actionBtn)
    actionBtn.click()
    await flush()

    assert.match(view.root.textContent, /Reporte Técnico|REPORT\.md/)
  } finally {
    view.cleanup()
  }
})
