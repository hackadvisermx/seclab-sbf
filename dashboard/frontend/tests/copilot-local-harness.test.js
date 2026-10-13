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

async function mount(api, route = { params: { id: 'test-harness-proj', type: 'engagement' } }) {
  globalThis.fixtureCopilotHarnessRoute = route
  globalThis.fixtureCopilotHarnessApi = new Proxy(api, {
    get: (target, key) => target[key] || (async () => ({}))
  })
  const source = await readFile(new URL('../src/views/EngagementDetailView.vue', import.meta.url), 'utf8')
  const { parse, compileScript } = await import('@vue/compiler-sfc')
  const { descriptor } = parse(source)
  let code = compileScript(descriptor, { id: 'engagement-copilot-harness', inlineTemplate: true }).content
    .replace(/from ["']vue["']/g, `from ${JSON.stringify(vueUrl)}`)
    .replace("import { useRoute, useRouter } from 'vue-router'", "const useRoute = () => globalThis.fixtureCopilotHarnessRoute; const useRouter = () => ({ push() {} })")
    .replace("import { api } from '../api'", 'const api = globalThis.fixtureCopilotHarnessApi')
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

test('botón e indicador de salud de modelos locales (Ollama/vLLM) en Copiloto', async () => {
  let probeProvider = null

  const apiMock = {
    getEngagement: async () => ({ id: 'test-harness-proj', name: 'Test Harness Proj', target: 'target.local' }),
    getCopilotModels: async () => ({ models: [], default: 'profile:local' }),
    getCopilotChatHistory: async () => ({ messages: [] }),
    getCopilotProviderHealth: async (prov) => {
      probeProvider = prov
      return {
        provider: prov,
        status: 'ONLINE',
        latency_ms: 18,
        models: ['llama3:latest', 'mistral:latest'],
        error: null,
      }
    },
    getScope: async () => ({ scope: {} }),
    getLogs: async () => ({ logs: [] }),
    getChecklist: async () => ({ items: [] }),
    getNotes: async () => ({ content: '' }),
    getReport: async () => ({ content: '' }),
    getFlags: async () => ({ flags: [] }),
    getLoot: async () => ({ credentials: [], files: [] }),
    getReconStatus: async () => ({ summary: {}, job: null }),
    getScopeBoundaries: async () => ({ boundaries: [] }),
  }

  const { root, cleanup } = await mount(apiMock)

  try {
    // Navegar a la pestaña de Copiloto
    await clickText(root, 'Copiloto')

    const checkBtn = root.querySelector('[data-testid="check-provider-health-btn"]')
    assert.ok(checkBtn, 'check-provider-health-btn should exist in Copiloto tab')
    assert.equal(checkBtn.disabled, false)

    checkBtn.click()
    await flush()

    assert.ok(probeProvider !== null, 'api.getCopilotProviderHealth should have been invoked')

    const pill = root.querySelector('[data-testid="copilot-provider-health-pill"]')
    assert.ok(pill, 'copilot-provider-health-pill should be rendered after check')
    assert.match(pill.textContent, /🟢 llama3:latest \(18ms\)/)
  } finally {
    cleanup()
  }
})
