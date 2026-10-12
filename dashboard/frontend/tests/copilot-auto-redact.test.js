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
  globalThis.fixtureRedactRoute = route
  globalThis.fixtureRedactApi = new Proxy(api, {
    get: (target, key) => target[key] || (async () => ({}))
  })
  const source = await readFile(new URL('../src/views/EngagementDetailView.vue', import.meta.url), 'utf8')
  const { parse, compileScript } = await import('@vue/compiler-sfc')
  const { descriptor } = parse(source)
  let code = compileScript(descriptor, { id: 'copilot-redact', inlineTemplate: true }).content
    .replace(/from ["']vue["']/g, `from ${JSON.stringify(vueUrl)}`)
    .replace("import { useRoute, useRouter } from 'vue-router'", "const useRoute = () => globalThis.fixtureRedactRoute; const useRouter = () => ({ push() {} })")
    .replace("import { api } from '../api'", 'const api = globalThis.fixtureRedactApi')
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

test('el botón de redacción automática enmascara secretos del contexto y actualiza la vista', async () => {
  let redactCalled = false
  const api = {
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
    getCopilotContext: async () => ({ context: 'Texto con secreto sk-12345678901234567890' }),
    reviewCopilotRequest: async () => ({
      context: 'Texto con secreto sk-12345678901234567890',
      context_review_token: 'token-abc',
      destination: { classification: 'LOCAL_LOOPBACK' }
    }),
    autoRedactText: async (text) => {
      redactCalled = true
      return {
        redacted_text: text.replace('sk-12345678901234567890', '[REDACTED_API_KEY]'),
        replacements_count: 1,
        redacted_types: ['api_key']
      }
    }
  }

  const view = await mount(api)
  try {
    await clickText(view.root, 'Copiloto Táctico')

    // Escribir mensaje y abrir modal de revisión
    const input = view.root.querySelector('input[placeholder*="Pregunta al copiloto"]')
    input.value = 'Revisa los hallazgos'
    input.dispatchEvent(new browser.window.Event('input'))
    await flush()

    await clickText(view.root, 'Revisar y enviar')

    // Verificar botón de redacción en el modal
    const redactBtn = view.root.querySelector('[data-testid="copilot-auto-redact-btn"]')
    assert.ok(redactBtn, 'Debe existir el botón de redacción automática en el modal')

    // Pulsar botón de redacción
    redactBtn.click()
    await flush()
    assert.ok(redactCalled, 'Debe llamarse al endpoint de redacción')

    // Verificar textarea actualizado y badge visible
    const badge = view.root.querySelector('[data-testid="copilot-redact-badge"]')
    assert.ok(badge, 'Debe mostrarse la insignia de secretos enmascarados')
    assert.match(badge.textContent, /1 secreto enmascarado/)

    const textarea = view.root.querySelector('textarea[aria-label="Contexto revisado para enviar"]')
    assert.ok(textarea)
    assert.match(textarea.value, /\[REDACTED_API_KEY\]/)
    assert.doesNotMatch(textarea.value, /sk-12345678901234567890/)
  } finally {
    view.cleanup()
  }
})
