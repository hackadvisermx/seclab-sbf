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
  globalThis.fixtureArtifactRedactRoute = route
  globalThis.fixtureArtifactRedactApi = new Proxy(api, {
    get: (target, key) => target[key] || (async () => ({}))
  })
  const source = await readFile(new URL('../src/views/EngagementDetailView.vue', import.meta.url), 'utf8')
  const { parse, compileScript } = await import('@vue/compiler-sfc')
  const { descriptor } = parse(source)
  let code = compileScript(descriptor, { id: 'engagement-artifact-redact', inlineTemplate: true }).content
    .replace(/from ["']vue["']/g, `from ${JSON.stringify(vueUrl)}`)
    .replace("import { useRoute, useRouter } from 'vue-router'", "const useRoute = () => globalThis.fixtureArtifactRedactRoute; const useRouter = () => ({ push() {} })")
    .replace("import { api } from '../api'", 'const api = globalThis.fixtureArtifactRedactApi')
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

test('el visor de artefactos permite conmutar redacción de secretos con indicador y máscara reactiva', async () => {
  const rawContent = 'API Request: Authorization: Bearer secret_token_12345\nDB config: password=SuperSecretPassword123'
  const redactedContent = 'API Request: Authorization: [REDACTED_BEARER_TOKEN]\nDB config: [REDACTED_PASSWORD]'

  let autoRedactCalled = false

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
    getArtifacts: async () => [
      { name: 'http_dump.txt', rel_path: 'recon/http_dump.txt', size: 2048 }
    ],
    getArtifactContent: async () => ({
      rel_path: 'recon/http_dump.txt',
      content: rawContent,
      size: 2048,
      modified: '2026-10-12 14:00:00',
      sha256: 'a'.repeat(64),
      preview_status: 'complete',
      fingerprint_status: 'available'
    }),
    autoRedactText: async (text) => {
      autoRedactCalled = true
      assert.equal(text, rawContent)
      return {
        redacted_text: redactedContent,
        replacements_count: 2
      }
    }
  }

  const { root, cleanup } = await mount(api)
  try {
    // 1. Navegar a pestaña de artefactos
    await clickText(root, 'Artefactos')

    // 2. Seleccionar el archivo 'http_dump.txt'
    await clickText(root, 'http_dump.txt')

    // 3. Verificar contenido inicial sin redacción
    const previewPre = root.querySelector('[data-testid="artifact-preview-content"]')
    assert.ok(previewPre, 'El elemento pre de contenido de artefacto debe existir')
    assert.match(previewPre.textContent, /secret_token_12345/)
    assert.match(previewPre.textContent, /SuperSecretPassword123/)

    const toggleBtn = root.querySelector('[data-testid="artifact-redact-toggle"]')
    assert.ok(toggleBtn, 'Botón de toggle de redacción debe existir')
    assert.match(toggleBtn.textContent, /Redactar Secretos/)

    // 4. Activar redacción de secretos
    toggleBtn.click()
    await flush()

    assert.equal(autoRedactCalled, true, 'api.autoRedactText debe haberse invocado')
    assert.match(toggleBtn.textContent, /Mostrar Original/)

    // 5. Comprobar insignia de secretos enmascarados
    const badge = root.querySelector('[data-testid="artifact-redacted-badge"]')
    assert.ok(badge, 'Insignia de secretos enmascarados debe mostrarse')
    assert.match(badge.textContent, /2 secretos enmascarados/)

    // 6. Comprobar que el texto pre ahora contiene las máscaras
    assert.match(previewPre.textContent, /\[REDACTED_BEARER_TOKEN\]/)
    assert.match(previewPre.textContent, /\[REDACTED_PASSWORD\]/)
    assert.ok(!previewPre.textContent.includes('secret_token_12345'))

    // 7. Desactivar redacción y comprobar restauración del contenido original
    toggleBtn.click()
    await flush()

    assert.match(toggleBtn.textContent, /Redactar Secretos/)
    assert.equal(root.querySelector('[data-testid="artifact-redacted-badge"]'), null)
    assert.match(previewPre.textContent, /secret_token_12345/)
  } finally {
    cleanup()
  }
})
