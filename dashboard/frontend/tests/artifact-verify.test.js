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
  globalThis.fixtureArtifactVerifyRoute = route
  globalThis.fixtureArtifactVerifyApi = new Proxy(api, {
    get: (target, key) => target[key] || (async () => ({}))
  })
  const source = await readFile(new URL('../src/views/EngagementDetailView.vue', import.meta.url), 'utf8')
  const { parse, compileScript } = await import('@vue/compiler-sfc')
  const { descriptor } = parse(source)
  let code = compileScript(descriptor, { id: 'engagement-artifact-verify', inlineTemplate: true }).content
    .replace(/from ["']vue["']/g, `from ${JSON.stringify(vueUrl)}`)
    .replace("import { useRoute, useRouter } from 'vue-router'", "const useRoute = () => globalThis.fixtureArtifactVerifyRoute; const useRouter = () => ({ push() {} })")
    .replace("import { api } from '../api'", 'const api = globalThis.fixtureArtifactVerifyApi')
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

const mockVerificationSuccess = {
  is_valid: true,
  engagement_id: 'test-proj',
  manifest_path: 'artifact-manifest.json',
  total_artifacts: 2,
  verified_count: 2,
  corrupted_count: 0,
  missing_count: 0,
  rejected_count: 0,
  details: [
    {
      path: 'recon/subdomains.txt',
      expected_sha256: 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
      computed_sha256: 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
      status: 'verified',
      error: null
    },
    {
      path: 'recon/live_hosts.txt',
      expected_sha256: 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
      computed_sha256: 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
      status: 'verified',
      error: null
    }
  ]
}

const mockVerificationTampered = {
  is_valid: false,
  engagement_id: 'test-proj',
  manifest_path: 'artifact-manifest.json',
  total_artifacts: 2,
  verified_count: 1,
  corrupted_count: 1,
  missing_count: 0,
  rejected_count: 0,
  details: [
    {
      path: 'recon/subdomains.txt',
      expected_sha256: 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
      computed_sha256: 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
      status: 'verified',
      error: null
    },
    {
      path: 'recon/live_hosts.txt',
      expected_sha256: 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
      computed_sha256: 'cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc',
      status: 'hash_mismatch',
      error: 'Hash SHA-256 no coincide; posible adulteración de evidencia.'
    }
  ]
}

test('botón de verificación de artefactos abre modal y renderiza resultado exitoso', async () => {
  let calledVerify = false

  const api = {
    getEngagementDetail: async () => ({
      name: 'Test Project',
      type: 'engagement',
      created_at: '2026-10-11T10:00:00Z',
      stats: { findings: 0, creds: 0, artifacts: 2 }
    }),
    getScope: async () => ({ target: 'example.com', authorization: { allow_passive: true } }),
    getFindings: async () => [],
    getLoot: async () => ({ credentials: [] }),
    getArtifacts: async () => [
      { name: 'subdomains.txt', rel_path: 'recon/subdomains.txt', size: 1024 }
    ],
    getReconStatus: async () => ({ running: false }),
    verifyArtifactManifest: async (id) => {
      calledVerify = true
      assert.equal(id, 'test-proj')
      return mockVerificationSuccess
    }
  }

  const { root, cleanup } = await mount(api)

  try {
    // 1. Ir a pestaña de Artefactos
    await clickText(root, 'Artefactos (recon/)')

    // 2. Localizar botón "Verificar Integridad"
    const verifyBtn = root.querySelector('[data-testid="verify-artifacts-btn"]')
    assert.ok(verifyBtn, 'Botón verify-artifacts-btn debe existir')
    verifyBtn.click()
    await flush()

    assert.equal(calledVerify, true, 'api.verifyArtifactManifest debe haber sido llamado')

    // 3. Modal abierto y verificado
    const modal = root.querySelector('[data-testid="artifact-verification-modal"]')
    assert.ok(modal, 'Modal de verificación debe estar presente')

    const statusBadge = root.querySelector('[data-testid="artifact-verification-status"]')
    assert.ok(statusBadge, 'Insignia de estado debe existir')
    assert.match(statusBadge.textContent, /INTEGRIDAD VÁLIDA/)

    // 4. Filas detalladas
    const row0 = root.querySelector('[data-testid="artifact-verify-row-0"]')
    const row1 = root.querySelector('[data-testid="artifact-verify-row-1"]')
    assert.ok(row0, 'Fila 0 debe existir')
    assert.ok(row1, 'Fila 1 debe existir')
    assert.match(row0.textContent, /recon\/subdomains\.txt/)
    assert.match(row1.textContent, /recon\/live_hosts\.txt/)
    assert.match(row0.textContent, /VÁLIDO/)
  } finally {
    cleanup()
  }
})

test('modal de verificación de artefactos refleja adulteración de hashes y estado comprometido', async () => {
  const api = {
    getEngagementDetail: async () => ({
      name: 'Test Project',
      type: 'engagement',
      created_at: '2026-10-11T10:00:00Z',
      stats: { findings: 0, creds: 0, artifacts: 2 }
    }),
    getScope: async () => ({ target: 'example.com', authorization: { allow_passive: true } }),
    getFindings: async () => [],
    getLoot: async () => ({ credentials: [] }),
    getArtifacts: async () => [
      { name: 'subdomains.txt', rel_path: 'recon/subdomains.txt', size: 1024 }
    ],
    getReconStatus: async () => ({ running: false }),
    verifyArtifactManifest: async () => mockVerificationTampered
  }

  const { root, cleanup } = await mount(api)

  try {
    await clickText(root, 'Artefactos (recon/)')
    const verifyBtn = root.querySelector('[data-testid="verify-artifacts-btn"]')
    verifyBtn.click()
    await flush()

    const modal = root.querySelector('[data-testid="artifact-verification-modal"]')
    assert.ok(modal, 'Modal debe estar abierto')

    const statusBadge = root.querySelector('[data-testid="artifact-verification-status"]')
    assert.match(statusBadge.textContent, /INTEGRIDAD COMPROMETIDA/)

    const row1 = root.querySelector('[data-testid="artifact-verify-row-1"]')
    assert.match(row1.textContent, /HASH ADULTERADO/)
    assert.match(row1.textContent, /posible adulteración de evidencia/)
  } finally {
    cleanup()
  }
})
