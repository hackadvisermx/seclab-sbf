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
  globalThis.fixturePlaybookRoute = route
  globalThis.fixturePlaybookApi = new Proxy(api, {
    get: (target, key) => target[key] || (async () => ({}))
  })
  const source = await readFile(new URL('../src/views/EngagementDetailView.vue', import.meta.url), 'utf8')
  const { parse, compileScript } = await import('@vue/compiler-sfc')
  const { descriptor } = parse(source)
  let code = compileScript(descriptor, { id: 'engagement-playbooks', inlineTemplate: true }).content
    .replace(/from ["']vue["']/g, `from ${JSON.stringify(vueUrl)}`)
    .replace("import { useRoute, useRouter } from 'vue-router'", "const useRoute = () => globalThis.fixturePlaybookRoute; const useRouter = () => ({ push() {} })")
    .replace("import { api } from '../api'", 'const api = globalThis.fixturePlaybookApi')
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

const mockPlaybooksList = [
  {
    id: 'pb_web_recon',
    title: 'Reconocimiento y Mapeo de Superficie Web',
    version: '1.0',
    category: 'web_audit',
    description: 'Identificación de hosts vivos y detección de endpoints.',
    author: 'SecLab-SBF',
    steps_count: 2,
    is_valid: true,
    file_path: 'web_recon.yaml'
  }
]

const mockPlaybookDetail = {
  is_valid: true,
  errors: [],
  playbook: {
    id: 'pb_web_recon',
    title: 'Reconocimiento y Mapeo de Superficie Web',
    version: '1.0',
    category: 'web_audit',
    description: 'Identificación de hosts vivos y detección de endpoints.',
    author: 'SecLab-SBF',
    parameters: {
      domain: {
        type: 'string',
        default: 'example.com',
        description: 'Dominio base a reconocer'
      }
    },
    steps: [
      {
        id: 'step_01_subfinder',
        title: 'Descubrimiento Pasivo de Subdominios',
        interaction_type: 'passive',
        command_template: 'subfinder -d {domain} -silent'
      },
      {
        id: 'step_02_httpx',
        title: 'Sondeo Activo HTTP/HTTPS',
        interaction_type: 'active_low',
        command_template: 'httpx -silent'
      }
    ]
  }
}

const mockScopeValidation = {
  is_valid: true,
  errors: [],
  scope_evaluation: {
    can_execute: true,
    blocked_steps_count: 0,
    steps_evaluation: [
      { step_id: 'step_01_subfinder', status: 'ALLOWED' },
      { step_id: 'step_02_httpx', status: 'ALLOWED' }
    ]
  }
}

const mockDryRunResult = {
  playbook_id: 'pb_web_recon',
  title: 'Reconocimiento y Mapeo de Superficie Web',
  status: 'SIMULATED',
  dry_run: true,
  total_steps: 2,
  executed_steps_count: 2,
  steps_results: [
    {
      step_id: 'step_01_subfinder',
      title: 'Descubrimiento Pasivo de Subdominios',
      interaction_type: 'passive',
      status: 'SIMULATED',
      command: 'subfinder -d example.com -silent',
      exit_code: 0,
      output: '[dry-run] Simulación completada'
    },
    {
      step_id: 'step_02_httpx',
      title: 'Sondeo Activo HTTP/HTTPS',
      interaction_type: 'active_low',
      status: 'SIMULATED',
      command: 'httpx -silent',
      exit_code: 0,
      output: '[dry-run] Simulación completada'
    }
  ]
}

test('pestaña de playbooks lista catálogo, inspecciona pasos y ejecuta simulación dry-run', async () => {
  let calledGetPlaybooks = false
  let calledGetPlaybook = false
  let calledRunPlaybook = false
  let runPayload = null

  const api = {
    getEngagementDetail: async () => ({
      name: 'Test Project',
      type: 'engagement',
      created_at: '2026-10-11T10:00:00Z',
      stats: { findings: 0, creds: 0, artifacts: 0 }
    }),
    getScope: async () => ({ target: 'example.com', authorization: { allow_passive: true, allow_active: true } }),
    getFindings: async () => [],
    getLoot: async () => ({ credentials: [] }),
    getArtifacts: async () => [],
    getReconStatus: async () => ({ running: false }),
    getPlaybooks: async (id) => {
      calledGetPlaybooks = true
      assert.equal(id, 'test-proj')
      return mockPlaybooksList
    },
    getPlaybook: async (id) => {
      calledGetPlaybook = true
      assert.equal(id, 'pb_web_recon')
      return mockPlaybookDetail
    },
    validatePlaybook: async () => mockScopeValidation,
    runPlaybook: async (id, payload) => {
      calledRunPlaybook = true
      assert.equal(id, 'pb_web_recon')
      runPayload = payload
      return mockDryRunResult
    }
  }

  const { root, cleanup } = await mount(api)

  try {
    // 1. Clic en pestaña Playbooks
    await clickText(root, 'Playbooks')
    assert.equal(calledGetPlaybooks, true, 'Debe invocar api.getPlaybooks al abrir la pestaña')
    assert.equal(calledGetPlaybook, true, 'Debe cargar el detalle del primer playbook')

    // 2. Verificar vista presente
    const playbooksView = root.querySelector('[data-testid="engagement-playbooks-view"]')
    assert.ok(playbooksView, 'La vista de playbooks debe estar presente en el DOM')

    // 3. Verificar metadata y badge de validez
    const validBadge = root.querySelector('[data-testid="playbook-valid-badge"]')
    assert.ok(validBadge, 'Badge de validez debe existir')
    assert.match(validBadge.textContent, /SCHEMA VÁLIDO/)

    // 4. Verificar pasos renderizados
    const step1 = root.querySelector('[data-testid="playbook-step-step_01_subfinder"]')
    const step2 = root.querySelector('[data-testid="playbook-step-step_02_httpx"]')
    assert.ok(step1, 'Paso 1 debe existir')
    assert.ok(step2, 'Paso 2 debe existir')

    const badge1 = root.querySelector('[data-testid="step-badge-step_01_subfinder"]')
    const badge2 = root.querySelector('[data-testid="step-badge-step_02_httpx"]')
    assert.match(badge1.textContent, /passive/)
    assert.match(badge2.textContent, /active_low/)

    // 5. Verificar input de parámetro 'domain'
    const domainInput = root.querySelector('[data-testid="param-input-domain"]')
    assert.ok(domainInput, 'Input de parámetro domain debe existir')
    assert.equal(domainInput.value, 'example.com')

    // 6. Ejecutar simulación Dry-Run
    await clickText(root, 'Simular (Dry-Run)')
    assert.equal(calledRunPlaybook, true, 'api.runPlaybook debe haber sido invocado')
    assert.equal(runPayload.dry_run, true, 'dry_run debe ser true')
    assert.equal(runPayload.parameters.domain, 'example.com')

    // 7. Verificar resumen de corrida
    const summary = root.querySelector('[data-testid="playbook-run-summary"]')
    assert.ok(summary, 'Resumen de corrida debe mostrarse tras la simulación')
    assert.match(summary.textContent, /SIMULATED/)

    const step1Status = root.querySelector('[data-testid="step-status-step_01_subfinder"]')
    assert.ok(step1Status, 'Insignia de estado de ejecución de paso 1 debe existir')
    assert.match(step1Status.textContent, /SIMULATED/)
  } finally {
    cleanup()
  }
})

test('pestaña de playbooks refleja bloqueos de alcance y estado BLOCKED', async () => {
  const mockBlockedRun = {
    playbook_id: 'pb_web_recon',
    title: 'Reconocimiento y Mapeo de Superficie Web',
    status: 'BLOCKED',
    dry_run: false,
    total_steps: 2,
    executed_steps_count: 1,
    reason: 'El playbook contiene pasos activos o no autorizados por target.yaml.',
    steps_results: [
      {
        step_id: 'step_02_httpx',
        title: 'Sondeo Activo HTTP/HTTPS',
        interaction_type: 'active_low',
        status: 'BLOCKED',
        command: 'httpx -silent',
        exit_code: 126,
        output: 'Bloqueado: La interacción activa no está autorizada en el contrato de alcance.'
      }
    ]
  }

  const api = {
    getEngagementDetail: async () => ({
      name: 'Test Project',
      type: 'engagement',
      created_at: '2026-10-11T10:00:00Z',
      stats: { findings: 0, creds: 0, artifacts: 0 }
    }),
    getScope: async () => ({ target: 'example.com', authorization: { allow_passive: true, allow_active: false } }),
    getFindings: async () => [],
    getLoot: async () => ({ credentials: [] }),
    getArtifacts: async () => [],
    getReconStatus: async () => ({ running: false }),
    getPlaybooks: async () => mockPlaybooksList,
    getPlaybook: async () => mockPlaybookDetail,
    validatePlaybook: async () => ({
      is_valid: true,
      errors: [],
      scope_evaluation: {
        can_execute: false,
        blocked_steps_count: 1,
        error: 'Paso step_02_httpx activo sin permiso'
      }
    }),
    runPlaybook: async () => mockBlockedRun
  }

  const { root, cleanup } = await mount(api)

  try {
    await clickText(root, 'Playbooks')

    // Verificar evaluación de alcance negativa
    const scopeAlert = root.querySelector('[data-testid="playbook-scope-eval"]')
    assert.ok(scopeAlert, 'Alerta de alcance debe existir')
    assert.match(scopeAlert.textContent, /BLOQUEADOS POR POLÍTICA DE ALCANCE/)

    // Ejecutar Playbook real
    await clickText(root, 'Ejecutar Playbook')

    // Verificar que el resultado es BLOCKED
    const runSummary = root.querySelector('[data-testid="playbook-run-summary"]')
    assert.ok(runSummary, 'Resumen de corrida debe existir')
    assert.match(runSummary.textContent, /BLOCKED/)
    assert.match(runSummary.textContent, /El playbook contiene pasos activos o no autorizados/)

    // Verificar que el paso 2 muestra BLOCKED y mensaje explicativo
    const step2Status = root.querySelector('[data-testid="step-status-step_02_httpx"]')
    assert.ok(step2Status, 'Badge de estado de paso bloqueado debe existir')
    assert.match(step2Status.textContent, /BLOCKED/)
  } finally {
    cleanup()
  }
})

test('pestaña de playbooks visualiza evidencia guardada e historial de corridas', async () => {
  const mockRun = {
    playbook_id: 'pb_web_recon',
    title: 'Reconocimiento y Mapeo de Superficie Web',
    status: 'COMPLETED',
    dry_run: false,
    total_steps: 2,
    executed_steps_count: 2,
    evidence_file: 'evidence/playbooks/pb_web_recon_20261012T200000Z.json',
    steps_results: []
  }

  const mockPastRuns = [
    {
      playbook_id: 'pb_web_recon',
      playbook_title: 'Reconocimiento y Mapeo de Superficie Web',
      timestamp: '2026-10-12T20:00:00Z',
      status: 'COMPLETED',
      dry_run: false,
      total_steps: 2,
      executed_steps_count: 2,
      file_name: 'pb_web_recon_20261012T200000Z.json',
      relative_path: 'evidence/playbooks/pb_web_recon_20261012T200000Z.json'
    }
  ]

  let calledGetRuns = false

  const api = {
    getEngagementDetail: async () => ({
      name: 'Test Project',
      type: 'engagement',
      created_at: '2026-10-11T10:00:00Z',
      stats: { findings: 0, creds: 0, artifacts: 0 }
    }),
    getScope: async () => ({ target: 'example.com', authorization: { allow_passive: true, allow_active: true } }),
    getFindings: async () => [],
    getLoot: async () => ({ credentials: [] }),
    getArtifacts: async () => [],
    getReconStatus: async () => ({ running: false }),
    getPlaybooks: async () => mockPlaybooksList,
    getPlaybook: async () => mockPlaybookDetail,
    validatePlaybook: async () => ({ is_valid: true, errors: [], scope_evaluation: null }),
    runPlaybook: async () => mockRun,
    getPlaybookRuns: async () => {
      calledGetRuns = true
      return mockPastRuns
    }
  }

  const { root, cleanup } = await mount(api)

  try {
    await clickText(root, 'Playbooks')
    assert.equal(calledGetRuns, true, 'getPlaybookRuns debe haberse invocado')

    // Verificar historial de corridas renderizado
    const historySection = root.querySelector('[data-testid="playbook-runs-history"]')
    assert.ok(historySection, 'Sección de historial debe existir')
    assert.match(historySection.textContent, /Historial de Evidencias/)

    const historyItem = root.querySelector('[data-testid="playbook-run-history-item"]')
    assert.ok(historyItem, 'Item de historial debe existir')
    assert.match(historyItem.textContent, /pb_web_recon_20261012T200000Z\.json/)

    // Ejecutar playbook y comprobar que el archivo de evidencia guardado se muestra en el resumen
    await clickText(root, 'Ejecutar Playbook')
    const evAlert = root.querySelector('[data-testid="playbook-evidence-file"]')
    assert.ok(evAlert, 'Badge de archivo de evidencia guardada debe existir')
    assert.match(evAlert.textContent, /evidence\/playbooks\/pb_web_recon_20261012T200000Z\.json/)
  } finally {
    cleanup()
  }
})


