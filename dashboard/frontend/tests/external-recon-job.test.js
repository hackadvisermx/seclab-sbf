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
  globalThis.fixtureExternalRoute = route
  globalThis.fixtureExternalApi = new Proxy(api, {
    get: (target, key) => target[key] || (async () => ({}))
  })
  const source = await readFile(new URL('../src/views/EngagementDetailView.vue', import.meta.url), 'utf8')
  const { parse, compileScript } = await import('@vue/compiler-sfc')
  const { descriptor } = parse(source)
  let code = compileScript(descriptor, { id: 'engagement-external-job', inlineTemplate: true }).content
    .replace(/from ["']vue["']/g, `from ${JSON.stringify(vueUrl)}`)
    .replace("import { useRoute, useRouter } from 'vue-router'", "const useRoute = () => globalThis.fixtureExternalRoute; const useRouter = () => ({ push() {} })")
    .replace("import { api } from '../api'", 'const api = globalThis.fixtureExternalApi')
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

test('Recon history renders record-external-job-btn, modal, and CLI_EXTERNAL badge', async () => {
  let recordCalled = false
  let recordedPayload = null

  const mockJobs = [
    {
      run_id: 'job-ext-1234',
      stage: 'probe',
      status: 'completed',
      dry_run: false,
      started_at: '2026-10-12T21:40:00Z',
      finished_at: '2026-10-12T21:40:05Z',
      scope_revision: 'abc',
      origin: 'cli-external',
      error: '[nmap] nmap -sS target.local',
    }
  ]

  const apiMock = {
    getEngagement: async () => ({ id: 'test-proj', name: 'Test Proj', target: 'target.local' }),
    getScope: async () => ({ scope: {} }),
    getFindings: async () => [],
    getLogs: async () => ({ logs: [] }),
    getChecklist: async () => ({ items: [] }),
    getNotes: async () => ({ content: '' }),
    getReport: async () => ({ content: '' }),
    getFlags: async () => ({ flags: [] }),
    getLoot: async () => ({ credentials: [], files: [] }),
    getReconStatus: async () => ({ summary: {}, job: null, discarded_out_of_scope: [] }),
    getReconHistory: async () => ({ jobs: mockJobs }),
    recordExternalReconJob: async (id, data) => {
      recordCalled = true
      recordedPayload = data
      return { success: true }
    },
    getScopeBoundaries: async () => ({ boundaries: [] }),
  }

  const { root, cleanup } = await mountEngagement(apiMock)

  try {
    // Cambiar a la pestaña de Reconocimiento
    await clickText(root, 'Reconocimiento')

    // Verificar presencia de la insignia CLI_EXTERNAL
    const badge = root.querySelector('[data-testid="cli-external-badge"]')
    assert.ok(badge, 'cli-external-badge should be rendered for external jobs')
    assert.equal(badge.textContent.trim(), 'CLI_EXTERNAL')

    // Verificar botón de ingestión
    const recordBtn = root.querySelector('[data-testid="record-external-job-btn"]')
    assert.ok(recordBtn, 'record-external-job-btn should exist')

    recordBtn.click()
    await flush()

    // Verificar modal abierto
    const modal = root.querySelector('[data-testid="record-external-job-modal"]')
    assert.ok(modal, 'record-external-job-modal should be visible')

    // Llenar formulario y enviar
    const toolInput = modal.querySelector('input')
    toolInput.value = 'httpx'
    toolInput.dispatchEvent(new browser.window.Event('input'))
    await flush()

    const submitBtn = modal.querySelector('[data-testid="submit-external-job-btn"]')
    assert.ok(submitBtn, 'submit-external-job-btn should exist')
    submitBtn.click()
    await flush()

    assert.equal(recordCalled, true)
    assert.equal(recordedPayload.tool, 'httpx')
  } finally {
    cleanup()
  }
})
