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
  globalThis.fixtureSigRoute = route
  globalThis.fixtureSigApi = new Proxy(api, {
    get: (target, key) => target[key] || (async () => ({}))
  })
  const source = await readFile(new URL('../src/views/EngagementDetailView.vue', import.meta.url), 'utf8')
  const { parse, compileScript } = await import('@vue/compiler-sfc')
  const { descriptor } = parse(source)
  let code = compileScript(descriptor, { id: 'engagement-artifact-signature', inlineTemplate: true }).content
    .replace(/from ["']vue["']/g, `from ${JSON.stringify(vueUrl)}`)
    .replace("import { useRoute, useRouter } from 'vue-router'", "const useRoute = () => globalThis.fixtureSigRoute; const useRouter = () => ({ push() {} })")
    .replace("import { api } from '../api'", 'const api = globalThis.fixtureSigApi')
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

test('modal de verificación de artefactos muestra sello de no repudio y permite firmar el manifiesto (V3-03ee)', async () => {
  let signCalled = false

  const mockVerifyResult = {
    is_valid: true,
    total_artifacts: 1,
    verified_count: 1,
    corrupted_count: 0,
    missing_count: 0,
    details: [],
    signature: {
      is_signed: true,
      valid: true,
      status: 'verified',
      signature: {
        signer: 'SecLab Auditor',
        signed_at: '2026-10-12T19:00:00Z',
        key_id: 'a1b2c3d4e5f6',
        manifest_hash: 'abc123hash',
      },
    },
  }

  const apiMock = {
    getEngagement: async () => ({ id: 'test-proj', name: 'Test Proj', target: 'target.local' }),
    verifyArtifactManifest: async () => mockVerifyResult,
    signArtifactManifest: async (id, signer, type) => {
      signCalled = true
      return { status: 'ok', signer }
    },
    getScope: async () => ({ scope: {} }),
    getFindings: async () => [],
    getLogs: async () => ({ logs: [] }),
    getChecklist: async () => ({ items: [] }),
    getNotes: async () => ({ content: '' }),
    getReport: async () => ({ content: '' }),
    getFlags: async () => ({ flags: [] }),
    getLoot: async () => ({ credentials: [], files: [] }),
    getReconStatus: async () => ({ summary: {}, job: null }),
    getScopeBoundaries: async () => ({ boundaries: [] }),
  }

  const { root, cleanup } = await mount(apiMock)

  try {
    // Abrir pestaña de artefactos y modal
    await clickText(root, 'Artefactos')

    const openVerifyBtn = root.querySelector('[data-testid="verify-artifacts-btn"]')
    assert.ok(openVerifyBtn, 'verify-artifacts-btn should exist in artifacts tab')
    openVerifyBtn.click()
    await flush()

    // Comprobar presencia de badge de firma
    const sigBadge = root.querySelector('[data-testid="artifact-signature-badge"]')
    assert.ok(sigBadge, 'artifact-signature-badge should exist in modal')
    assert.equal(sigBadge.textContent.trim(), 'FIRMADO Y VERIFICADO')

    // Pulsar botón de firmar manifiesto
    const signBtn = root.querySelector('[data-testid="sign-artifact-manifest-btn"]')
    assert.ok(signBtn, 'sign-artifact-manifest-btn should exist')
    signBtn.click()
    await flush()

    assert.equal(signCalled, true, 'api.signArtifactManifest must be called')
  } finally {
    cleanup()
  }
})
