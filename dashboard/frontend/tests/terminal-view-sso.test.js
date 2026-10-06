import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { createRequire } from 'node:module'
import { pathToFileURL } from 'node:url'
import { test } from 'node:test'
import { JSDOM } from 'jsdom'

// Fase 114 / backlog A10: la terminal embebida debe apuntar al proxy de
// mismo origen del dashboard (que inyecta la autenticación de ttyd del
// lado del servidor) en vez de al puerto :7681 directo, que forzaba un
// segundo inicio de sesión HTTP Basic separado del dashboard.

const browser = new JSDOM('<body></body>', { url: 'http://localhost:8080' })
for (const name of ['window', 'document', 'Element', 'SVGElement', 'HTMLElement', 'Node']) globalThis[name] = browser.window[name]
const { createApp, nextTick } = await import('vue')
const vueUrl = pathToFileURL(createRequire(import.meta.url).resolve('vue/dist/vue.runtime.esm-bundler.js')).href

async function mountTerminalView() {
  const source = await readFile(new URL('../src/views/TerminalView.vue', import.meta.url), 'utf8')
  const { parse, compileScript } = await import('@vue/compiler-sfc')
  const { descriptor } = parse(source)
  const compiled = compileScript(descriptor, { id: 'views/TerminalView.vue', inlineTemplate: true })
  const code = compiled.content.replace(/from ["']vue["']/g, `from ${JSON.stringify(vueUrl)}`)
  const component = (await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}#${Math.random()}`)).default
  const root = document.createElement('div')
  document.body.append(root)
  const app = createApp(component)
  app.mount(root)
  await flush()
  return { root, cleanup() { app.unmount(); root.remove() } }
}

async function flush() {
  await nextTick()
  await new Promise(resolve => setTimeout(resolve, 0))
  await nextTick()
}

test('el iframe de la terminal apunta al proxy de mismo origen, no al puerto :7681 directo', async () => {
  const { root, cleanup } = await mountTerminalView()
  try {
    const iframe = root.querySelector('iframe')
    assert.ok(iframe, 'el iframe de la terminal debe estar presente por defecto (conectado)')
    const src = iframe.getAttribute('src')
    assert.equal(src, 'http://localhost:8080/api/v1/terminal/')
    assert.doesNotMatch(src, /:7681/, 'no debe apuntar directo al puerto de ttyd')
  } finally {
    cleanup()
  }
})

test('el enlace "ir a pestaña externa" tambien usa el proxy de mismo origen cuando esta desconectada', async () => {
  const { root, cleanup } = await mountTerminalView()
  try {
    // Desconectar para que se muestre el estado "pausada" con el enlace externo.
    const disconnectBtn = Array.from(root.querySelectorAll('button')).find(b => b.textContent.includes('Desconectar'))
    disconnectBtn.click()
    await flush()
    const externalLink = Array.from(root.querySelectorAll('a')).find(a => a.textContent.includes('Pestaña Externa'))
    assert.ok(externalLink)
    assert.equal(externalLink.getAttribute('href'), 'http://localhost:8080/api/v1/terminal/')
  } finally {
    cleanup()
  }
})
