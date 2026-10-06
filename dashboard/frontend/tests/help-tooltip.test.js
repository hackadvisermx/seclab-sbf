import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { createRequire } from 'node:module'
import { pathToFileURL } from 'node:url'
import { test } from 'node:test'
import { JSDOM } from 'jsdom'

// Fase 112 / backlog A8: ayuda contextual corta sobre la jerga del
// dashboard (Scope Guard, Evidence-First, control negativo, patrones gf).

const browser = new JSDOM('<body></body>', { url: 'http://localhost' })
for (const name of ['window', 'document', 'Element', 'SVGElement', 'HTMLElement', 'Node']) globalThis[name] = browser.window[name]
const { createApp, nextTick } = await import('vue')
const vueUrl = pathToFileURL(createRequire(import.meta.url).resolve('vue/dist/vue.runtime.esm-bundler.js')).href

async function mountComponent(filename, props = {}, slotContent = '') {
  const source = await readFile(new URL(`../src/${filename}`, import.meta.url), 'utf8')
  const { parse, compileScript } = await import('@vue/compiler-sfc')
  const { descriptor } = parse(source)
  const compiled = compileScript(descriptor, { id: filename, inlineTemplate: true })
  const code = compiled.content.replace(/from ["']vue["']/g, `from ${JSON.stringify(vueUrl)}`)
  const component = (await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}#${Math.random()}`)).default
  const root = document.createElement('div')
  document.body.append(root)
  const app = createApp({
    components: { Target: component },
    props: [],
    template: `<Target label="${props.label}">${slotContent}</Target>`,
  })
  app.mount(root)
  await flush()
  return { root, cleanup() { app.unmount(); root.remove() } }
}

async function flush() {
  await nextTick()
  await new Promise(resolve => setTimeout(resolve, 0))
  await nextTick()
}

test('el popover esta cerrado por defecto y se abre/cierra al pulsar el boton', async () => {
  const { root, cleanup } = await mountComponent('components/HelpTooltip.vue', { label: 'Scope Guard' }, 'Explicacion de prueba')
  try {
    assert.equal(root.querySelector('[role="tooltip"]'), null, 'El popover no debe mostrarse por defecto')
    const button = root.querySelector('button')
    assert.equal(button.getAttribute('aria-label'), 'Qué significa Scope Guard')

    button.click()
    await flush()
    const tooltip = root.querySelector('[role="tooltip"]')
    assert.ok(tooltip, 'El popover debe abrirse al pulsar el boton')
    assert.match(tooltip.textContent, /Explicacion de prueba/)
    assert.match(tooltip.textContent, /Scope Guard/)

    button.click()
    await flush()
    assert.equal(root.querySelector('[role="tooltip"]'), null, 'Un segundo clic debe cerrarlo')
  } finally {
    cleanup()
  }
})

test('perder el foco cierra el popover', async () => {
  const { root, cleanup } = await mountComponent('components/HelpTooltip.vue', { label: 'Evidence-First' }, 'texto')
  try {
    const button = root.querySelector('button')
    button.click()
    await flush()
    assert.ok(root.querySelector('[role="tooltip"]'))
    button.dispatchEvent(new browser.window.Event('blur'))
    await flush()
    assert.equal(root.querySelector('[role="tooltip"]'), null)
  } finally {
    cleanup()
  }
})

test('EngagementDetailView usa HelpTooltip en los 4 terminos de jerga clave', async () => {
  const source = await readFile(new URL('../src/views/EngagementDetailView.vue', import.meta.url), 'utf8')
  assert.match(source, /import HelpTooltip from ['"]\.\.\/components\/HelpTooltip\.vue['"]/)
  for (const label of ['Scope Guard', 'Patrones gf', 'Evidence-First', 'Control Negativo y BDT']) {
    assert.match(
      source,
      new RegExp(`<HelpTooltip label="${label}"`),
      `Falta HelpTooltip para "${label}"`
    )
  }
})
