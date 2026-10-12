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
  globalThis.fixtureConsentRoute = route
  globalThis.fixtureConsentApi = new Proxy(api, {
    get: (target, key) => target[key] || (async () => ({}))
  })
  const source = await readFile(new URL('../src/views/EngagementDetailView.vue', import.meta.url), 'utf8')
  const { parse, compileScript } = await import('@vue/compiler-sfc')
  const { descriptor } = parse(source)
  let code = compileScript(descriptor, { id: 'engagement-consent', inlineTemplate: true }).content
    .replace(/from ["']vue["']/g, `from ${JSON.stringify(vueUrl)}`)
    .replace("import { useRoute, useRouter } from 'vue-router'", "const useRoute = () => globalThis.fixtureConsentRoute; const useRouter = () => ({ push() {} })")
    .replace("import { api } from '../api'", 'const api = globalThis.fixtureConsentApi')
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

test('Copilot consent history button opens modal and displays audit records', async () => {
  const consentEntries = [
    {
      timestamp: '2026-10-12T21:30:00Z',
      engagement_id: 'test-proj',
      agent_id: 'triage-agent',
      provider: 'openrouter',
      model: 'claude-3.5-sonnet',
      network_tier: 'PUBLIC_REMOTE',
      prompt_hash: '1234567890abcdef1234567890abcdef',
      context_hash: 'abcdef1234567890abcdef1234567890',
      context_bytes: 540,
      token: 'tok-abc-123',
      status: 'consented',
    }
  ]

  let consentHistoryCalled = false
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
    getReconStatus: async () => ({ summary: {}, job: null }),
    getReconHistory: async () => ({ jobs: [] }),
    getCopilotAgents: async () => [{ id: 'triage-agent', name: 'Triaje', skill: 'triage' }],
    getCopilotChatHistory: async () => [],
    getCopilotConsentHistory: async (id) => {
      consentHistoryCalled = true
      return consentEntries
    },
    getScopeBoundaries: async () => ({ boundaries: [] }),
    getChecklist: async () => ({ checklist: [] }),
    getNotes: async () => ({ content: '' }),
  }

  const { root, cleanup } = await mountEngagement(apiMock)

  try {
    await clickText(root, 'Copiloto Táctico')

    const btn = root.querySelector('[data-testid="copilot-consent-history-btn"]')
    assert.ok(btn, 'copilot-consent-history-btn should exist')

    btn.click()
    await flush()

    assert.equal(consentHistoryCalled, true)
    const modal = root.querySelector('[data-testid="copilot-consent-modal"]')
    assert.ok(modal, 'copilot-consent-modal should be visible')

    const items = root.querySelectorAll('[data-testid="consent-entry-item"]')
    assert.equal(items.length, 1)
    assert.ok(items[0].textContent.includes('PUBLIC_REMOTE'))
    assert.ok(items[0].textContent.includes('triage-agent'))
  } finally {
    cleanup()
  }
})
