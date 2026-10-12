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

async function mount(api, route = { params: { id: 'test-scope-proj', type: 'engagement' } }) {
  globalThis.fixtureScopeRoute = route
  globalThis.fixtureScopeApi = new Proxy(api, {
    get: (target, key) => target[key] || (async () => ({})),
  })
  const source = await readFile(new URL('../src/views/EngagementDetailView.vue', import.meta.url), 'utf8')
  const { parse, compileScript } = await import('@vue/compiler-sfc')
  const { descriptor } = parse(source)
  let code = compileScript(descriptor, { id: 'engagement-scope-revisions', inlineTemplate: true }).content
    .replace(/from ["']vue["']/g, `from ${JSON.stringify(vueUrl)}`)
    .replace("import { useRoute, useRouter } from 'vue-router'", "const useRoute = () => globalThis.fixtureScopeRoute; const useRouter = () => ({ push() {} })")
    .replace("import { api } from '../api'", 'const api = globalThis.fixtureScopeApi')
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
  return {
    root,
    cleanup() {
      app.unmount()
      root.remove()
    },
  }
}

test('permite consultar el historial de revisiones y diffs de target.yaml en modal de alcance (V3-01h)', async () => {
  let calledRevisions = false
  const fakeRevisions = [
    {
      revision_id: 'a1b2c3d4',
      timestamp: '2026-10-12T16:20:00Z',
      action: 'updated',
      diff: '--- target.yaml (anterior)\n+++ target.yaml (nuevo)\n@@ -1,2 +1,3 @@\n+      - api.target.local\n',
      previous_sha256: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
      new_sha256: 'ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb',
      author: 'tester',
    },
  ]

  const api = {
    getEngagementDetail: async () => ({
      name: 'Scope Test Project',
      type: 'engagement',
      created_at: '2026-10-11T10:00:00Z',
      stats: { findings: 0, creds: 0, artifacts: 0 },
    }),
    getScope: async () => ({
      engagement: { id: 'test-scope-proj' },
      authorization: { allow_passive: true, allow_active: false, reference: 'Test' },
      scope: { in_scope: { domains: ['target.local'] } },
    }),
    getFindings: async () => [],
    getLoot: async () => ({ credentials: [] }),
    getArtifacts: async () => [],
    getReconStatus: async () => ({ running: false }),
    getScopeRevisions: async (id) => {
      calledRevisions = true
      assert.equal(id, 'test-scope-proj')
      return fakeRevisions
    },
  }

  const { root, cleanup } = await mount(api)

  try {
    // 1. Por defecto estamos en la pestaña Alcance
    const revBtn = root.querySelector('[data-testid="scope-revisions-btn"]')
    assert.ok(revBtn, 'El botón de revisiones de alcance debe estar visible en la pestaña Alcance')

    // 2. Hacer clic en el botón de revisiones
    revBtn.click()
    await flush()

    assert.equal(calledRevisions, true, 'api.getScopeRevisions debe ser llamado al abrir el modal')

    // 3. Verificar que el modal de revisiones de alcance está abierto
    const modal = root.querySelector('[data-testid="scope-revisions-modal"]')
    assert.ok(modal, 'El modal de revisiones de alcance debe estar en el DOM')

    // 4. Verificar contenido de la revisión
    const revItem = root.querySelector('[data-testid="scope-revision-item-0"]')
    assert.ok(revItem, 'El elemento de revisión debe mostrarse')
    assert.match(revItem.textContent, /#a1b2c3d4/)
    assert.match(revItem.textContent, /updated/)
    assert.match(revItem.textContent, /api\.target\.local/)

    // 5. Cerrar el modal
    const closeBtn = root.querySelector('[data-testid="close-scope-revisions-btn"]')
    assert.ok(closeBtn, 'El botón de cerrar debe estar disponible')
    closeBtn.click()
    await flush()

    assert.equal(root.querySelector('[data-testid="scope-revisions-modal"]'), null, 'El modal debe cerrarse')
  } finally {
    cleanup()
  }
})
