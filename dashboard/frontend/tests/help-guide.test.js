import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { createRequire } from 'node:module'
import { pathToFileURL } from 'node:url'
import { test } from 'node:test'
import { JSDOM } from 'jsdom'
import { parse, compileScript } from '@vue/compiler-sfc'

const browser = new JSDOM('<body></body>', { url: 'http://localhost' })
for (const name of ['window', 'document', 'Element', 'SVGElement', 'HTMLElement', 'Node']) {
  globalThis[name] = browser.window[name]
}
const { createApp, nextTick } = await import('vue')
const vueUrl = pathToFileURL(createRequire(import.meta.url).resolve('vue/dist/vue.runtime.esm-bundler.js')).href

async function mountHelpView(api) {
  globalThis.fixtureHelpApi = api
  const source = await readFile(new URL('../src/views/HelpView.vue', import.meta.url), 'utf8')
  const { descriptor } = parse(source)
  const compiled = compileScript(descriptor, { id: 'HelpView.vue', inlineTemplate: true })
  const code = compiled.content
    .replace(/from ["']vue["']/g, `from ${JSON.stringify(vueUrl)}`)
    .replace("import { api } from '../api'", 'const api = globalThis.fixtureHelpApi')

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
  await new Promise(resolve => setTimeout(resolve, 15))
  await nextTick()
}

test('HelpView muestra la pestaña Guía del Operador por defecto con iframe hacia /api/v1/help/guide', async () => {
  const mockApi = {
    getCheatsheet: async () => [],
    getSkills: async () => [],
    getSkillDetail: async () => ({ content: '' }),
  }

  const { root, cleanup } = await mountHelpView(mockApi)
  try {
    const text = root.textContent
    assert.match(text, /Guía del Operador/)
    assert.match(text, /Misión 1/)
    assert.match(text, /Auditoría Web \/ API/)
    assert.match(text, /Misión 2/)
    assert.match(text, /Retos CTF & Máquinas/)
    assert.match(text, /Misión 3/)
    assert.match(text, /Agentes IA & Hermes/)
    assert.match(text, /Misión 4/)
    assert.match(text, /Pivoting & Redes/)
    assert.match(text, /Misión 5/)
    assert.match(text, /Centro de Mando/)

    const iframe = root.querySelector('iframe')
    assert.ok(iframe, 'El iframe de la guía debe estar presente')
    assert.equal(iframe.getAttribute('src'), '/api/v1/help/guide')

    const externalLink = root.querySelector('a[href="/api/v1/help/guide"]')
    assert.ok(externalLink, 'El enlace para pantalla completa debe existir')
    assert.equal(externalLink.getAttribute('target'), '_blank')
  } finally {
    cleanup()
  }
})

test('HelpView permite navegar entre las diferentes pestañas de ayuda', async () => {
  const mockApi = {
    getCheatsheet: async () => [
      { category: 'recon', title: 'Assetfinder', command: 'assetfinder target.com', description: 'Buscar subdominios' }
    ],
    getSkills: async () => [
      { id: 'recon-profiling', title: 'Recon & Profiling', description: 'Descubrimiento pasivo' }
    ],
    getSkillDetail: async (id) => ({ id, content: '# Playbook ' + id }),
  }

  const { root, cleanup } = await mountHelpView(mockApi)
  try {
    const buttons = root.querySelectorAll('button')
    const accessBtn = Array.from(buttons).find(b => b.textContent.includes('Datos de Acceso'))
    assert.ok(accessBtn, 'Botón de Datos de Acceso debe existir')

    accessBtn.click()
    await flush()

    let text = root.textContent
    assert.match(text, /Puertos y Servicios Internos/)
    assert.match(text, /Web Terminal \(ttyd\)/)
    assert.match(text, /Tactical Dashboard & Hermes/)

    const cheatBtn = Array.from(root.querySelectorAll('button')).find(b => b.textContent.includes('Catálogo pt-cheat'))
    assert.ok(cheatBtn, 'Botón de Cheatsheet debe existir')
    cheatBtn.click()
    await flush()

    text = root.textContent
    assert.match(text, /Assetfinder/)
    assert.match(text, /assetfinder target\.com/)
  } finally {
    cleanup()
  }
})
