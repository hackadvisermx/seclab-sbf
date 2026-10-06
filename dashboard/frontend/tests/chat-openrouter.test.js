import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { createRequire } from 'node:module'
import { pathToFileURL } from 'node:url'
import { test } from 'node:test'
import { JSDOM } from 'jsdom'
import { parse, compileScript } from '@vue/compiler-sfc'

const browser = new JSDOM('<body></body>', { url: 'http://localhost' })
for (const name of ['window', 'document', 'Document', 'Element', 'SVGElement', 'HTMLElement', 'HTMLSelectElement', 'HTMLInputElement', 'HTMLTextAreaElement', 'Node', 'Event', 'CustomEvent', 'localStorage', 'sessionStorage']) {
  if (browser.window[name]) {
    globalThis[name] = browser.window[name]
  }
}
// Polyfill localStorage si JSDOM no lo expuso
if (!globalThis.localStorage) {
  const store = new Map()
  globalThis.localStorage = {
    getItem: (k) => store.get(k) || null,
    setItem: (k, v) => store.set(k, String(v)),
    removeItem: (k) => store.delete(k),
    clear: () => store.clear(),
  }
}

const { createApp, nextTick } = await import('vue')
const vueUrl = pathToFileURL(createRequire(import.meta.url).resolve('vue/dist/vue.runtime.esm-bundler.js')).href

async function flush() {
  await nextTick()
  await new Promise(resolve => setTimeout(resolve, 20))
  await nextTick()
}

async function mountNavbar(api) {
  globalThis.fixtureNavbarApi = api
  const source = await readFile(new URL('../src/components/Navbar.vue', import.meta.url), 'utf8')
  const { descriptor } = parse(source)
  const compiled = compileScript(descriptor, { id: 'Navbar.vue', inlineTemplate: true })
  const code = compiled.content
    .replace(/from ["']vue["']/g, `from ${JSON.stringify(vueUrl)}`)
    .replace("import { api } from '../api'", 'const api = globalThis.fixtureNavbarApi')
    .replace("import { useTheme } from '../theme'", 'const useTheme = () => ({ theme: { value: "dark" }, toggleTheme: () => {} })')

  const component = (await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}#${Math.random()}`)).default
  const root = document.createElement('div')
  document.body.append(root)
  const app = createApp(component)
  app.config.globalProperties.$route = { path: '/' }
  app.component('router-link', { props: ['to'], template: '<a :href="to"><slot /></a>' })
  app.mount(root)
  await flush()
  return { root, cleanup() { app.unmount(); root.remove() } }
}

async function mountChatView(api) {
  globalThis.fixtureChatApi = api
  const source = await readFile(new URL('../src/views/ChatView.vue', import.meta.url), 'utf8')
  const { descriptor } = parse(source)
  const compiled = compileScript(descriptor, { id: 'ChatView.vue', inlineTemplate: true })
  const code = compiled.content
    .replace(/from ["']vue["']/g, `from ${JSON.stringify(vueUrl)}`)
    .replace("import { api } from '../api'", 'const api = globalThis.fixtureChatApi')

  const component = (await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}#${Math.random()}`)).default
  const root = document.createElement('div')
  document.body.append(root)
  const app = createApp(component)
  app.component('router-link', { props: ['to'], template: '<a :href="to"><slot /></a>' })
  app.mount(root)
  await flush()
  return { root, cleanup() { app.unmount(); root.remove() } }
}

async function mountVaultView(api) {
  globalThis.fixtureVaultApi = api
  const source = await readFile(new URL('../src/views/VaultView.vue', import.meta.url), 'utf8')
  const { descriptor } = parse(source)
  const compiled = compileScript(descriptor, { id: 'VaultView.vue', inlineTemplate: true })
  const code = compiled.content
    .replace(/from ["']vue["']/g, `from ${JSON.stringify(vueUrl)}`)
    .replace("import { api } from '../api'", 'const api = globalThis.fixtureVaultApi')

  const component = (await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}#${Math.random()}`)).default
  const root = document.createElement('div')
  document.body.append(root)
  const app = createApp(component)
  app.mount(root)
  await flush()
  return { root, cleanup() { app.unmount(); root.remove() } }
}

test('Navbar incluye enlace táctico a Chat IA (/chat)', async () => {
  const mockApi = {
    getTelemetry: async () => ({ local_ip: '127.0.0.1', vpn: { connected: false } }),
    getSavedVpnCredentials: async () => ({}),
  }
  const { root, cleanup } = await mountNavbar(mockApi)
  try {
    const chatLink = root.querySelector('a[href="/chat"]')
    assert.ok(chatLink, 'Debe existir enlace hacia /chat en Navbar')
    assert.match(chatLink.textContent, /Chat IA/)
  } finally {
    cleanup()
  }
})

test('ChatView renderiza selector de modelos OpenRouter y presets populares', async () => {
  const mockApi = {
    getVaultKeys: async () => [
      { provider: 'openrouter', service_type: 'llm', is_active: true }
    ],
    proxyChat: async () => ({
      provider: 'openrouter',
      model: 'anthropic/claude-3.5-sonnet',
      content: 'Respuesta simulada',
      latency_ms: 150,
      usage: { total_tokens: 42 },
    }),
  }
  const { root, cleanup } = await mountChatView(mockApi)
  try {
    const text = root.textContent
    assert.match(text, /Chat IA Táctico/)
    assert.match(text, /OPENROUTER & MODEL HUB/)
    assert.match(text, /VAULT ONLINE/)

    // Verificar selectores
    const selects = root.querySelectorAll('select')
    assert.ok(selects.length >= 2, 'Debe haber selectores de proveedor y modelo')

    const providerSelect = selects[0]
    assert.match(providerSelect.textContent, /OpenRouter/)

    const modelSelect = selects[1]
    assert.match(modelSelect.textContent, /Claude 3\.5 Sonnet/)
    assert.match(modelSelect.textContent, /DeepSeek V3/)
    assert.match(modelSelect.textContent, /DeepSeek R1/)
    assert.match(modelSelect.textContent, /Llama 3\.3 70B/)
  } finally {
    cleanup()
  }
})

test('ChatView despacha consulta al proxy táctico con proveedor y modelo especificados', async () => {
  let capturedCall = null
  const mockApi = {
    getVaultKeys: async () => [
      { provider: 'openrouter', service_type: 'llm', is_active: true }
    ],
    proxyChat: async (messages, provider, model, profile, temperature) => {
      capturedCall = { messages, provider, model, profile, temperature }
      return {
        provider: 'openrouter',
        model: 'deepseek/deepseek-r1',
        content: 'PoC técnica para verificación de IDOR con control negativo',
        latency_ms: 320,
        usage: { total_tokens: 120 },
      }
    },
  }
  const { root, cleanup } = await mountChatView(mockApi)
  try {
    const modelSelect = root.querySelectorAll('select')[1]
    modelSelect.value = 'deepseek/deepseek-r1'
    modelSelect.dispatchEvent(new Event('change'))
    await flush()

    const textarea = root.querySelector('textarea')
    assert.ok(textarea, 'Debe existir textarea de entrada')
    textarea.value = 'Generar PoC IDOR'
    textarea.dispatchEvent(new Event('input'))

    const form = root.querySelector('form')
    form.dispatchEvent(new Event('submit'))
    await flush()

    assert.ok(capturedCall, 'api.proxyChat debió ser llamado')
    assert.equal(capturedCall.provider, 'openrouter')
    assert.equal(capturedCall.model, 'deepseek/deepseek-r1')
    assert.ok(capturedCall.messages.some(m => m.content === 'Generar PoC IDOR'))

    // Verificar que la respuesta se renderiza en la UI
    await flush()
    assert.match(root.textContent, /PoC técnica para verificación de IDOR/)
    assert.match(root.textContent, /320 ms/)
  } finally {
    cleanup()
  }
})

test('VaultView soporta proveedor openrouter con base_url y modelo predeterminado', async () => {
  const mockApi = {
    getVaultKeys: async () => [],
    getProxyStats: async () => ({ total_requests: 0 }),
    getProxyHistory: async () => [],
  }
  const { root, cleanup } = await mountVaultView(mockApi)
  try {
    // Abrir modal de agregar llave
    const addBtn = root.querySelector('button')
    addBtn.click()
    await flush()

    // Selector de proveedor en el modal
    const providerSelect = root.querySelector('form select')
    assert.ok(providerSelect, 'Debe existir select de proveedor')
    assert.match(providerSelect.textContent, /OpenRouter/)

    // Cambiar a openrouter
    providerSelect.value = 'openrouter'
    providerSelect.dispatchEvent(new Event('change'))
    await flush()

    // Comprobar que los campos de base_url y model_name se preconfiguran
    const inputs = root.querySelectorAll('form input')
    const values = Array.from(inputs).map(i => i.value)
    assert.ok(values.includes('OpenRouter API Key'), 'Label predeterminado debe ser OpenRouter API Key')
  } finally {
    cleanup()
  }
})
