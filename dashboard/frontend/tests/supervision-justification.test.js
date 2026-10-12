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
  globalThis.fixtureSupervisionRoute = route
  globalThis.fixtureSupervisionApi = new Proxy(api, {
    get: (target, key) => target[key] || (async () => ({})),
  })
  const source = await readFile(new URL('../src/views/EngagementDetailView.vue', import.meta.url), 'utf8')
  const { parse, compileScript } = await import('@vue/compiler-sfc')
  const { descriptor } = parse(source)
  let code = compileScript(descriptor, { id: 'engagement-supervision-justification', inlineTemplate: true }).content
    .replace(/from ["']vue["']/g, `from ${JSON.stringify(vueUrl)}`)
    .replace("import { useRoute, useRouter } from 'vue-router'", "const useRoute = () => globalThis.fixtureSupervisionRoute; const useRouter = () => ({ push() {} })")
    .replace("import { api } from '../api'", 'const api = globalThis.fixtureSupervisionApi')
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

async function clickText(root, text) {
  const button = [...root.querySelectorAll('button')].find(b => b.textContent.trim().includes(text))
  assert.ok(button, `Missing button containing "${text}"`)
  button.click()
  await flush()
}

test('permite registrar y visualizar justificación de decisiones en checkpoints de supervisión (V3-06d)', async () => {
  const mockSupervisionData = {
    engagement_id: 'test-proj',
    overall_status: 'WARNING',
    checkpoints: [
      {
        id: 'cp_scope',
        name: 'Alcance Autorizado (target.yaml)',
        status: 'PASS',
        detail: 'Alcance declarado.',
        recommendation: 'Mantener vigencia.',
        is_justified: true,
        learner_response: {
          checkpoint_id: 'cp_scope',
          justification: 'Autorizado con el CISO de Acme.',
          learner_action: 'revisar_contrato',
          updated_at: '2026-10-12T15:00:00Z',
        },
      },
      {
        id: 'cp_recon',
        name: 'Reconocimiento y Huellas',
        status: 'WARNING',
        detail: 'Sin hosts vivos detectados.',
        recommendation: 'Lanzar sondeo inicial.',
        is_justified: false,
        learner_response: null,
      },
    ],
    blocking_issues: [],
    warnings: [],
    pending_actions: [],
  }

  let respondedPayload = null
  const api = {
    getEngagementDetail: async () => ({
      name: 'Test Project',
      type: 'engagement',
      created_at: '2026-10-11T10:00:00Z',
      stats: { findings: 0, creds: 0, artifacts: 0 },
    }),
    getScope: async () => ({ target: 'example.com', authorization: { allow_passive: true } }),
    getFindings: async () => [],
    getLoot: async () => ({ credentials: [] }),
    getArtifacts: async () => [],
    getReconStatus: async () => ({ running: false }),
    getSupervision: async () => mockSupervisionData,
    respondSupervisionCheckpoint: async (id, cpId, payload, type) => {
      respondedPayload = { id, cpId, payload, type }
      return { status: 'ok', checkpoint_id: cpId, learner_response: payload }
    },
  }

  const { root, cleanup } = await mount(api)

  try {
    // 1. Abrir la pestaña de Supervisión Pedagógica
    await clickText(root, 'Supervisión Pedagógica')

    // 2. Verificar que la justificación existente se visualiza
    const existingResp = root.querySelector('[data-testid="checkpoint-learner-response-cp_scope"]')
    assert.ok(existingResp, 'La justificación existente de cp_scope debe mostrarse')
    assert.match(existingResp.textContent, /Autorizado con el CISO de Acme/)
    assert.match(existingResp.textContent, /revisar_contrato/)

    // 3. Introducir nueva justificación en cp_recon
    const textarea = root.querySelector('[data-testid="checkpoint-justification-input-cp_recon"]')
    assert.ok(textarea, 'El textarea para justificación de cp_recon debe existir')
    textarea.value = 'Hosts no responden a ping ICMP, procederé con sondeo SYN en puerto 443.'
    textarea.dispatchEvent(new browser.window.Event('input'))
    await flush()

    // 4. Hacer clic en el botón de registrar justificación
    const saveBtn = root.querySelector('[data-testid="checkpoint-save-response-btn-cp_recon"]')
    assert.ok(saveBtn, 'El botón de guardar justificación debe existir')
    saveBtn.click()
    await flush()

    // 5. Verificar que la API fue llamada con los parámetros correctos
    assert.ok(respondedPayload, 'api.respondSupervisionCheckpoint debe haber sido invocado')
    assert.equal(respondedPayload.id, 'test-proj')
    assert.equal(respondedPayload.cpId, 'cp_recon')
    assert.equal(respondedPayload.type, 'engagement')
    assert.match(respondedPayload.payload.justification, /Hosts no responden a ping ICMP/)
  } finally {
    cleanup()
  }
})
