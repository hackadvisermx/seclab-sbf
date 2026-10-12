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
  globalThis.fixtureRevisionsRoute = route
  globalThis.fixtureRevisionsApi = new Proxy(api, {
    get: (target, key) => target[key] || (async () => ({}))
  })
  const source = await readFile(new URL('../src/views/EngagementDetailView.vue', import.meta.url), 'utf8')
  const { parse, compileScript } = await import('@vue/compiler-sfc')
  const { descriptor } = parse(source)
  let code = compileScript(descriptor, { id: 'engagement-revisions', inlineTemplate: true }).content
    .replace(/from ["']vue["']/g, `from ${JSON.stringify(vueUrl)}`)
    .replace("import { useRoute, useRouter } from 'vue-router'", "const useRoute = () => globalThis.fixtureRevisionsRoute; const useRouter = () => ({ push() {} })")
    .replace("import { api } from '../api'", 'const api = globalThis.fixtureRevisionsApi')
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

const mockFinding = {
  slug: 'xss_stored',
  filename: 'xss_stored.md',
  source_sha256: 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
  frontmatter: {
    title: 'Stored XSS en Perfil',
    severity: 'HIGH',
    status: 'PROVEN',
    asset: 'example.com',
    cvss_score: 7.5
  },
  body: 'Prueba de concepto de XSS almacenado.'
}

const mockRevisionsData = {
  slug: 'xss_stored',
  total_revisions: 2,
  revisions: [
    {
      revision_id: 'rev001',
      timestamp: '2026-10-12T10:00:00Z',
      action: 'create',
      slug: 'xss_stored',
      title: 'Stored XSS en Perfil',
      severity: 'MEDIUM',
      status: 'CANDIDATE',
      previous_sha256: null,
      new_sha256: 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
      modified_fields: ['title', 'severity', 'status'],
      author: 'tester'
    },
    {
      revision_id: 'rev002',
      timestamp: '2026-10-12T11:00:00Z',
      action: 'update',
      slug: 'xss_stored',
      title: 'Stored XSS en Perfil',
      severity: 'HIGH',
      status: 'PROVEN',
      previous_sha256: 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
      new_sha256: 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
      modified_fields: ['severity', 'status', 'verification_rationale'],
      field_diffs: {
        severity: { old: 'MEDIUM', new: 'HIGH' },
        status: { old: 'CANDIDATE', new: 'PROVEN' }
      },
      author: 'tester'
    }
  ]
}

test('botón de revisiones abre modal con historial de auditoría de la ficha', async () => {
  let calledRevisions = false

  const api = {
    getEngagementDetail: async () => ({
      name: 'Test Project',
      type: 'engagement',
      created_at: '2026-10-11T10:00:00Z',
      stats: { findings: 1, creds: 0, artifacts: 0 }
    }),
    getScope: async () => ({ target: 'example.com', authorization: { allow_passive: true } }),
    getFindings: async () => [mockFinding],
    getLoot: async () => ({ credentials: [] }),
    getArtifacts: async () => [],
    getReconStatus: async () => ({ running: false }),
    getFindingRevisions: async (engId, slug) => {
      calledRevisions = true
      assert.equal(engId, 'test-proj')
      assert.equal(slug, 'xss_stored')
      return mockRevisionsData
    }
  }

  const { root, cleanup } = await mount(api)

  try {
    // 1. Ir a la pestaña de Hallazgos
    await clickText(root, 'Hallazgos (evidence/)')

    // 2. Localizar botón de revisiones
    const revBtn = root.querySelector('[data-testid="finding-revisions-btn-xss_stored"]')
    assert.ok(revBtn, 'El botón de revisiones de la ficha debe existir')

    // 3. Clic en Revisiones
    revBtn.click()
    await flush()

    assert.equal(calledRevisions, true, 'api.getFindingRevisions debe haber sido llamado')

    // 4. Verificar modal abierto
    const modal = root.querySelector('[data-testid="finding-revisions-modal"]')
    assert.ok(modal, 'Modal de revisiones debe estar en el DOM')
    assert.match(modal.textContent, /Historial de Revisiones: xss_stored/)

    // 5. Verificar items de revisión
    const item0 = root.querySelector('[data-testid="revision-item-0"]')
    const item1 = root.querySelector('[data-testid="revision-item-1"]')
    assert.ok(item0, 'Revisión 0 (create) debe existir')
    assert.ok(item1, 'Revisión 1 (update) debe existir')

    assert.match(item0.textContent, /create/)
    assert.match(item0.textContent, /CANDIDATE/)
    assert.match(item1.textContent, /update/)
    assert.match(item1.textContent, /PROVEN/)
    assert.match(item1.textContent, /Campos modificados: severity, status, verification_rationale/)
    assert.match(item1.textContent, /aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/)

    // 6. Cerrar modal
    await clickText(modal, 'Cerrar')
    const modalClosed = root.querySelector('[data-testid="finding-revisions-modal"]')
    assert.equal(modalClosed, null, 'Modal debe haberse cerrado')
  } finally {
    cleanup()
  }
})

test('comparador visual de versiones muestra diferencias de campos entre revisiones', async () => {
  const api = {
    getEngagementDetail: async () => ({
      name: 'Test Project',
      type: 'engagement',
      created_at: '2026-10-11T10:00:00Z',
      stats: { findings: 1, creds: 0, artifacts: 0 }
    }),
    getScope: async () => ({ target: 'example.com', authorization: { allow_passive: true } }),
    getFindings: async () => [mockFinding],
    getLoot: async () => ({ credentials: [] }),
    getArtifacts: async () => [],
    getReconStatus: async () => ({ running: false }),
    getFindingRevisions: async () => mockRevisionsData
  }

  const { root, cleanup } = await mount(api)
  try {
    await clickText(root, 'Hallazgos (evidence/)')
    const revBtn = root.querySelector('[data-testid="finding-revisions-btn-xss_stored"]')
    revBtn.click()
    await flush()

    // 1. Verificar visual diff inline en la revisión 1
    const fieldDiffs = root.querySelector('[data-testid="revision-field-diffs"]')
    assert.ok(fieldDiffs, 'Deben renderizarse los cambios detallados inline')
    assert.match(fieldDiffs.textContent, /severity:/)
    assert.match(fieldDiffs.textContent, /MEDIUM/)
    assert.match(fieldDiffs.textContent, /HIGH/)

    // 2. Abrir comparador visual
    const toggleBtn = root.querySelector('[data-testid="toggle-comparator-btn"]')
    assert.ok(toggleBtn, 'Debe existir el botón para alternar el comparador')
    toggleBtn.click()
    await flush()

    // 3. Verificar panel del comparador
    const panel = root.querySelector('[data-testid="revision-comparator-panel"]')
    assert.ok(panel, 'Debe renderizarse el panel del comparador')

    const diffView = root.querySelector('[data-testid="revisions-diff-view"]')
    assert.ok(diffView, 'Debe renderizarse la vista de diferencias')
    assert.match(diffView.textContent, /Diferencias detectadas/)
  } finally {
    cleanup()
  }
})

