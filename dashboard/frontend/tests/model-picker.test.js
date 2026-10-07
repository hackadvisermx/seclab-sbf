import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { createRequire } from 'node:module'
import { pathToFileURL } from 'node:url'
import { test } from 'node:test'
import { JSDOM } from 'jsdom'
import { parse, compileScript } from '@vue/compiler-sfc'

// Fase 136: combobox de modelo compartido entre VaultView (modelo inicial de
// una llave del Vault) y ChatView (modelo activo del Chat IA Táctico), en
// reemplazo del <select> + <input> de búsqueda + botón de recarga separados
// que existían antes. El owner probó esa versión en vivo y pidió algo más
// parecido a un buscador flotante de una sola pieza (como el selector de
// modelos de OpenCode): un único campo que es a la vez disparador y
// buscador, con una lista filtrable al teclear y navegación por teclado.

const browser = new JSDOM('<body></body>', { url: 'http://localhost' })
for (const name of ['window', 'document', 'Element', 'SVGElement', 'HTMLElement', 'HTMLInputElement', 'Node', 'Event', 'MouseEvent', 'KeyboardEvent']) {
  if (browser.window[name]) globalThis[name] = browser.window[name]
}

const { createApp, h, reactive, nextTick } = await import('vue')
const vueUrl = pathToFileURL(createRequire(import.meta.url).resolve('vue/dist/vue.runtime.esm-bundler.js')).href

async function flush() {
  await nextTick()
  await new Promise(resolve => setTimeout(resolve, 10))
  await nextTick()
}

async function loadModelPicker() {
  const source = await readFile(new URL('../src/components/ModelPicker.vue', import.meta.url), 'utf8')
  const { descriptor } = parse(source)
  const compiled = compileScript(descriptor, { id: 'ModelPicker.vue', inlineTemplate: true })
  const code = compiled.content.replace(/from ["']vue["']/g, `from ${JSON.stringify(vueUrl)}`)
  return (await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}#${Math.random()}`)).default
}
const ModelPicker = await loadModelPicker()

const sampleModels = [
  { id: 'anthropic/claude-3.5-sonnet', name: 'Claude 3.5 Sonnet' },
  { id: 'deepseek/deepseek-r1', name: 'DeepSeek R1' },
  { id: 'meta-llama/llama-3.3-70b-instruct', name: 'Llama 3.3 70B' },
]

function mountPicker(initialProps = {}) {
  const state = reactive({
    modelValue: '',
    models: sampleModels,
    loading: false,
    error: '',
    allowCustom: false,
    placeholder: 'Elegir modelo',
    ...initialProps,
  })
  const events = { refresh: 0, updates: [] }
  const app = createApp({
    render() {
      return h(ModelPicker, {
        modelValue: state.modelValue,
        models: state.models,
        loading: state.loading,
        error: state.error,
        allowCustom: state.allowCustom,
        placeholder: state.placeholder,
        'onUpdate:modelValue': (v) => { state.modelValue = v; events.updates.push(v) },
        onRefresh: () => { events.refresh++ },
      })
    },
  })
  const root = document.createElement('div')
  document.body.append(root)
  app.mount(root)
  return { root, state, events, cleanup() { app.unmount(); root.remove() } }
}

function getInput(root) {
  return root.querySelector('input[role="combobox"]')
}
function getOptions(root) {
  return Array.from(root.querySelectorAll('[role="option"]'))
}

test('cerrado, muestra "name — id" del modelo seleccionado; sin selección, queda vacío con el placeholder', async () => {
  const { root, cleanup } = mountPicker({ modelValue: 'deepseek/deepseek-r1' })
  try {
    await flush()
    assert.equal(getInput(root).value, 'DeepSeek R1 — deepseek/deepseek-r1')
    assert.equal(getInput(root).getAttribute('placeholder'), 'Elegir modelo')
  } finally { cleanup() }
})

test('al enfocar se abre el panel con todos los modelos y limpia el campo para buscar', async () => {
  const { root, cleanup } = mountPicker({ modelValue: 'deepseek/deepseek-r1' })
  try {
    await flush()
    getInput(root).focus()
    await flush()
    assert.equal(getInput(root).getAttribute('aria-expanded'), 'true')
    assert.equal(getInput(root).value, '')
    assert.equal(getOptions(root).filter(o => o.textContent.includes('—')).length, 3)
  } finally { cleanup() }
})

test('filtra al teclear, por nombre o por id', async () => {
  const { root, cleanup } = mountPicker()
  try {
    const input = getInput(root)
    input.focus(); await flush()
    input.value = 'r1'; input.dispatchEvent(new Event('input')); await flush()
    const texts = getOptions(root).map(o => o.textContent)
    assert.ok(texts.some(t => t.includes('DeepSeek R1')))
    assert.ok(!texts.some(t => t.includes('Claude 3.5 Sonnet')))
  } finally { cleanup() }
})

test('clic (mousedown, no click) en una fila selecciona el modelo y cierra el panel', async () => {
  // mousedown.prevent evita el bug clásico de combobox donde el blur del
  // input cierra el panel antes de que un `click` llegue a la fila.
  const { root, state, cleanup } = mountPicker()
  try {
    const input = getInput(root)
    input.focus(); await flush()
    const option = getOptions(root).find(o => o.textContent.includes('DeepSeek R1'))
    option.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true }))
    await flush()
    assert.equal(state.modelValue, 'deepseek/deepseek-r1')
    assert.equal(getInput(root).getAttribute('aria-expanded'), 'false')
  } finally { cleanup() }
})

test('navegación con flechas resalta las filas y Enter selecciona la resaltada', async () => {
  const { root, state, cleanup } = mountPicker()
  try {
    const input = getInput(root)
    input.focus(); await flush()
    // Arranca resaltado en el primer modelo (Claude); una flecha abajo pasa
    // al segundo (DeepSeek R1).
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true, cancelable: true }))
    await flush()
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true }))
    await flush()
    assert.equal(state.modelValue, 'deepseek/deepseek-r1')
  } finally { cleanup() }
})

test('Escape cierra el panel sin cambiar la selección', async () => {
  const { root, state, cleanup } = mountPicker({ modelValue: 'anthropic/claude-3.5-sonnet' })
  try {
    const input = getInput(root)
    input.focus(); await flush()
    input.value = 'deepseek'; input.dispatchEvent(new Event('input')); await flush()
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }))
    await flush()
    assert.equal(state.modelValue, 'anthropic/claude-3.5-sonnet')
    assert.equal(getInput(root).getAttribute('aria-expanded'), 'false')
  } finally { cleanup() }
})

test('la fila "Actualizar modelos" emite refresh sin cerrar el panel', async () => {
  const { root, events, cleanup } = mountPicker()
  try {
    const input = getInput(root)
    input.focus(); await flush()
    const refreshRow = getOptions(root).find(o => o.textContent.includes('Actualizar modelos'))
    assert.ok(refreshRow)
    refreshRow.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true }))
    await flush()
    assert.equal(events.refresh, 1)
    assert.equal(getInput(root).getAttribute('aria-expanded'), 'true', 'el panel debe seguir abierto tras refrescar')
  } finally { cleanup() }
})

test('allowCustom agrega la fila "Modelo personalizado" y selecciona el sentinel "custom"', async () => {
  const { root, state, cleanup } = mountPicker({ allowCustom: true })
  try {
    const input = getInput(root)
    input.focus(); await flush()
    const customRow = getOptions(root).find(o => o.textContent.includes('Modelo personalizado'))
    assert.ok(customRow, 'solo debe aparecer con allowCustom')
    customRow.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true }))
    await flush()
    assert.equal(state.modelValue, 'custom')
  } finally { cleanup() }
})

test('sin allowCustom, no aparece la fila de modelo personalizado', async () => {
  const { root, cleanup } = mountPicker({ allowCustom: false })
  try {
    const input = getInput(root)
    input.focus(); await flush()
    assert.ok(!getOptions(root).some(o => o.textContent.includes('Modelo personalizado')))
  } finally { cleanup() }
})

test('loading muestra "Consultando…" y oculta la lista', async () => {
  const { root, cleanup } = mountPicker({ loading: true })
  try {
    const input = getInput(root)
    input.focus(); await flush()
    assert.match(root.textContent, /Consultando…/)
    assert.equal(getOptions(root).length, 0)
  } finally { cleanup() }
})

test('error se muestra dentro del panel, con role=alert', async () => {
  const { root, cleanup } = mountPicker({ error: 'No se pudo consultar el catálogo (HTTP 401)' })
  try {
    const input = getInput(root)
    input.focus(); await flush()
    const alertEl = root.querySelector('[role="alert"]')
    assert.ok(alertEl)
    assert.match(alertEl.textContent, /HTTP 401/)
  } finally { cleanup() }
})

test('sin coincidencias, muestra el aviso pero conserva la fila de Actualizar', async () => {
  const { root, cleanup } = mountPicker()
  try {
    const input = getInput(root)
    input.focus(); await flush()
    input.value = 'xyz-no-existe'; input.dispatchEvent(new Event('input')); await flush()
    assert.match(root.textContent, /Sin coincidencias/)
    assert.ok(getOptions(root).some(o => o.textContent.includes('Actualizar modelos')))
  } finally { cleanup() }
})
