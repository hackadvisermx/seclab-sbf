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

const fixtureCatalog = {
  models: [
    { id: 'anthropic/claude-3.5-sonnet', name: 'Claude 3.5 Sonnet' },
    { id: 'deepseek/deepseek-chat', name: 'DeepSeek V3' },
    { id: 'deepseek/deepseek-r1', name: 'DeepSeek R1' },
    { id: 'meta-llama/llama-3.3-70b-instruct', name: 'Llama 3.3 70B' },
    { id: 'fixture/new-model', name: 'Nuevo modelo accesible' },
  ],
  default_model: 'anthropic/claude-3.5-sonnet',
}

async function mountChatView(api) {
  globalThis.fixtureChatApi = { getProviderModels: async () => fixtureCatalog, ...api }
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
  globalThis.fixtureVaultApi = { previewProviderModels: async () => fixtureCatalog, ...api }
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

test('VaultView permite editar llave existente actualizando base_url y modelo via updateVaultKey', async () => {
  let updatedProvider = null
  let updatedPayload = null
  const mockApi = {
    getVaultKeys: async () => [
      {
        id: 1,
        provider: 'custom_llm',
        label: 'Open Router',
        service_type: 'llm',
        masked_key: 'sk-or-••••••••••••••••3456',
        base_url: ' https://openrouter.ai/api/v1',
        model_name: 'anthropic/claude-3.5-sonnet',
        is_active: true,
        status: 'error',
        status_message: "Fallo de conexión: Request URL is missing an 'http://' or 'https://' protocol.",
        created_at: '2026-10-05T20:00:00Z',
      }
    ],
    getProxyStats: async () => ({ total_requests: 0 }),
    getProxyHistory: async () => [],
    updateVaultKey: async (provider, payload) => {
      updatedProvider = provider
      updatedPayload = payload
      return { status: 'ok' }
    },
  }
  const { root, cleanup } = await mountVaultView(mockApi)
  try {
    // Buscar botón de Editar en la tarjeta
    const editBtn = Array.from(root.querySelectorAll('button')).find(b => b.textContent.includes('Editar'))
    assert.ok(editBtn, 'Debe existir botón Editar en la tarjeta')
    editBtn.click()
    await flush()

    // Comprobar título del modal en modo edición
    const modalTitle = root.querySelector('.fixed h2')
    assert.match(modalTitle.textContent, /Editar Configuración: Open Router/)

    // Comprobar que el select de proveedor está deshabilitado
    const providerSelect = root.querySelector('form select')
    assert.equal(providerSelect.disabled, true, 'Proveedor debe estar deshabilitado en edición')

    // Modificar base_url
    const urlInput = root.querySelector('input[placeholder="http://localhost:11434/v1"]') || Array.from(root.querySelectorAll('form input')).find(i => i.value.includes('openrouter.ai'))
    assert.ok(urlInput, 'Debe existir input de base_url')
    urlInput.value = 'https://openrouter.ai/api/v1'
    urlInput.dispatchEvent(new Event('input'))

    await flush()
    Array.from(root.querySelectorAll('button')).find(b => b.textContent.includes('Consultar modelos')).click()
    await flush()
    // Enviar formulario
    const form = root.querySelector('form')
    form.dispatchEvent(new Event('submit'))
    await flush()

    // Verificar llamada a api.updateVaultKey
    assert.equal(updatedProvider, 'custom_llm')
    assert.ok(updatedPayload)
    assert.equal(updatedPayload.label, 'Open Router')
    assert.equal(updatedPayload.base_url, 'https://openrouter.ai/api/v1')
    assert.equal(updatedPayload.model_name, 'anthropic/claude-3.5-sonnet')
    assert.equal(updatedPayload.is_active, true)
    assert.equal(updatedPayload.api_key, undefined, 'api_key no debe enviarse si se dejó en blanco')
  } finally {
    cleanup()
  }
})



test('Chat usa la clave custom_llm de OpenRouter y su catálogo sin presets fijos', async () => {
  let call
  localStorage.clear()
  localStorage.setItem('seclab_chat_provider', 'custom_llm')
  const { root, cleanup } = await mountChatView({
    getVaultKeys: async () => [{ provider: 'custom_llm', service_type: 'llm', is_active: true, base_url: ' https://openrouter.ai/api/v1 ', model_name: 'fixture/new-model' }],
    getProviderModels: async provider => { assert.equal(provider, 'custom_llm'); return { ...fixtureCatalog, default_model: 'fixture/new-model' } },
    proxyChat: async (messages, provider, model) => { call = { provider, model }; return { content: 'Respuesta', model } },
  })
  try {
    assert.match(root.querySelectorAll('select')[1].textContent, /Nuevo modelo accesible/)
    assert.equal(root.querySelectorAll('select')[1].value, 'fixture/new-model')
    const input = root.querySelector('textarea')
    input.value = 'Hola'
    input.dispatchEvent(new Event('input'))
    await flush()
    input.dispatchEvent(new browser.window.KeyboardEvent('keydown', { key: 'Enter', bubbles: true }))
    await flush()
    assert.deepEqual(call, { provider: 'custom_llm', model: 'fixture/new-model' })
  } finally { cleanup(); localStorage.clear() }
})

test('Vault consulta catálogo antes de guardar clave y persiste modelo seleccionado', async () => {
  let saved
  let preview
  const { root, cleanup } = await mountVaultView({
    getVaultKeys: async () => [], getProxyStats: async () => ({}), getProxyHistory: async () => [],
    previewProviderModels: async payload => { preview = payload; return fixtureCatalog },
    upsertVaultKey: async payload => { saved = { ...payload } },
  })
  try {
    root.querySelector('button').click(); await flush()
    const provider = root.querySelector('form select')
    provider.value = 'openrouter'; provider.dispatchEvent(new Event('change')); await flush()
    const key = root.querySelector('input[type="password"]')
    key.value = 'fixture-token'; key.dispatchEvent(new Event('input')); await flush()
    Array.from(root.querySelectorAll('button')).find(b => b.textContent.includes('Consultar modelos')).click(); await flush()
    assert.equal(preview.api_key, 'fixture-token')
    assert.equal(saved, undefined)
    const model = root.querySelectorAll('form select')[1]
    model.value = 'fixture/new-model'; model.dispatchEvent(new Event('change')); await flush()
    root.querySelector('form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })); await flush()
    assert.equal(saved.model_name, 'fixture/new-model')
  } finally { cleanup() }
})


test('Chat evita enviar un modelo retirado y muestra errores del catálogo', async () => {
  localStorage.clear()
  let calls = 0
  const { root, cleanup } = await mountChatView({
    getVaultKeys: async () => [{ provider: 'openrouter', service_type: 'llm', is_active: true, model_name: 'vendor/removed' }],
    getProviderModels: async () => ({ models: [{ id: 'vendor/current', name: 'Actual' }], default_model: 'vendor/removed' }),
    proxyChat: async () => { calls++ },
  })
  try {
    assert.equal(root.querySelectorAll('select')[1].value, '')
    const input = root.querySelector('textarea')
    input.value = 'Hola'; input.dispatchEvent(new Event('input')); await flush()
    input.dispatchEvent(new browser.window.KeyboardEvent('keydown', { key: 'Enter', bubbles: true })); await flush()
    assert.equal(calls, 0)
    assert.match(root.textContent, /elige un modelo/)
  } finally { cleanup(); localStorage.clear() }
})
