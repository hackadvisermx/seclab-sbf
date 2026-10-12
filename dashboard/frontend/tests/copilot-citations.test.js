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
  globalThis.fixtureCitationRoute = route
  globalThis.fixtureCitationApi = new Proxy(api, {
    get: (target, key) => target[key] || (async () => ({}))
  })
  const source = await readFile(new URL('../src/views/EngagementDetailView.vue', import.meta.url), 'utf8')
  const { parse, compileScript } = await import('@vue/compiler-sfc')
  const { descriptor } = parse(source)
  let code = compileScript(descriptor, { id: 'copilot-citations', inlineTemplate: true }).content
    .replace(/from ["']vue["']/g, `from ${JSON.stringify(vueUrl)}`)
    .replace("import { useRoute, useRouter } from 'vue-router'", "const useRoute = () => globalThis.fixtureCitationRoute; const useRouter = () => ({ push() {} })")
    .replace("import { api } from '../api'", 'const api = globalThis.fixtureCitationApi')
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

test('las respuestas del Copiloto renderizan citas navegables y permiten saltar a la sección correspondiente', async () => {
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
    getCopilotContext: async () => ({ context: 'Contexto de prueba' }),
    reviewCopilotRequest: async () => ({
      context: 'Contexto de prueba',
      context_review_token: 'token-123',
      destination: { classification: 'LOCAL_LOOPBACK' }
    }),
    sendCopilotChat: async () => ({
      content: 'Basado en `evidence/xss.md` y `target.yaml`.',
      model: 'test-model',
      latency_ms: 120,
      citations: [
        { path: 'evidence/xss.md', exists: true, sha256: 'a'.repeat(64), size: 1024 },
        { path: 'target.yaml', exists: true, sha256: 'b'.repeat(64), size: 512 }
      ]
    })
  }

  const view = await mount(api)
  try {
    await clickText(view.root, 'Copiloto Táctico')

    // Ingresar prompt y simular flujo de envío
    const input = view.root.querySelector('input[placeholder*="Pregunta al copiloto"]')
    assert.ok(input, 'Debe existir input de mensaje')
    input.value = '¿Qué vulnerabilidades hay?'
    input.dispatchEvent(new browser.window.Event('input'))
    await flush()

    // Abrir modal de revisión
    await clickText(view.root, 'Revisar y enviar')

    // Confirmar envío en el modal
    const sendBtn = [...view.root.querySelectorAll('button')].find(b => b.textContent.includes('Enviar contenido revisado'))
    assert.ok(sendBtn, 'Debe existir botón de envío en el modal')
    sendBtn.click()
    await flush()

    // Verificar que se renderizó la lista de citas
    const citationsList = view.root.querySelector('[data-testid="copilot-citations-list"]')
    assert.ok(citationsList, 'Debe renderizarse la lista de citas en el mensaje del asistente')

    const citationLinks = view.root.querySelectorAll('[data-testid="copilot-citation-link"]')
    assert.equal(citationLinks.length, 2, 'Deben renderizarse 2 enlaces de citas')
    assert.match(citationLinks[0].textContent, /evidence\/xss\.md/)
    assert.match(citationLinks[1].textContent, /target\.yaml/)

    // Verificar indicador proactivo de cobertura (100% verificada) y barra de sesión (V3-05k)
    const coverageBadge = view.root.querySelector('[data-testid="copilot-citation-coverage-badge"]')
    assert.ok(coverageBadge, 'Debe renderizarse el badge de cobertura de citas')
    assert.match(coverageBadge.textContent, /100% verificada/)

    const sessionStats = view.root.querySelector('[data-testid="copilot-session-citation-stats"]')
    assert.ok(sessionStats, 'Debe renderizarse la barra de estadísticas de citas de la sesión')
    assert.match(sessionStats.textContent, /100%/)

    // Hacer clic en la cita de evidence/xss.md y verificar cambio a tab de findings
    citationLinks[0].click()
    await flush()

    const findingsContainer = view.root.querySelector('[data-testid="findings-view"]') || view.root.querySelector('.tactical-card')
    assert.ok(findingsContainer)
  } finally {
    view.cleanup()
  }
})

test('las respuestas sin citas muestran advertencia proactiva de contenido no anclado y cobertura parcial cuando faltan fuentes', async () => {
  let callCount = 0
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
    getCopilotContext: async () => ({ context: 'Contexto de prueba' }),
    reviewCopilotRequest: async () => ({
      context: 'Contexto de prueba',
      context_review_token: 'token-test',
      destination: { classification: 'LOCAL_LOOPBACK' }
    }),
    sendCopilotChat: async () => {
      callCount++
      if (callCount === 1) {
        // Respuesta sin citas directas
        return {
          content: 'Respuesta general explicativa sin citas a archivos.',
          model: 'test-model',
          citations: []
        }
      } else {
        // Respuesta con citas parciales (1 existe, 1 falta)
        return {
          content: 'Cita parcial a artefactos.',
          model: 'test-model',
          citations: [
            { path: 'evidence/ok.md', exists: true, sha256: 'a'.repeat(64), size: 100 },
            { path: 'evidence/missing.md', exists: false, sha256: null, size: null }
          ]
        }
      }
    }
  }

  const view = await mount(api)
  try {
    await clickText(view.root, 'Copiloto Táctico')

    // 1. Mensaje 1: Respuesta sin citas
    const input = view.root.querySelector('input[placeholder*="Pregunta al copiloto"]')
    input.value = '¿Cómo funciona el proxy?'
    input.dispatchEvent(new browser.window.Event('input'))
    await flush()

    await clickText(view.root, 'Revisar y enviar')
    const sendBtn = [...view.root.querySelectorAll('button')].find(b => b.textContent.includes('Enviar contenido revisado'))
    sendBtn.click()
    await flush()

    // Comprobar aviso de respuesta no anclada a fuentes
    const unanchoredNotice = view.root.querySelector('[data-testid="copilot-citation-unanchored-notice"]')
    assert.ok(unanchoredNotice, 'Debe mostrar aviso de respuesta sin fuentes citadas')
    assert.match(unanchoredNotice.textContent, /sin fuentes locales citadas/)

    const coverageNone = view.root.querySelector('[data-testid="copilot-citation-coverage-badge"]')
    assert.ok(coverageNone)
    assert.match(coverageNone.textContent, /Sin fuentes citadas/)

    // 2. Mensaje 2: Respuesta con citas parciales
    input.value = '¿Qué evidencias existen?'
    input.dispatchEvent(new browser.window.Event('input'))
    await flush()

    await clickText(view.root, 'Revisar y enviar')
    const sendBtn2 = [...view.root.querySelectorAll('button')].find(b => b.textContent.includes('Enviar contenido revisado'))
    sendBtn2.click()
    await flush()

    const badges = view.root.querySelectorAll('[data-testid="copilot-citation-coverage-badge"]')
    assert.equal(badges.length, 2)
    assert.match(badges[1].textContent, /50% parcial/)
  } finally {
    view.cleanup()
  }
})

