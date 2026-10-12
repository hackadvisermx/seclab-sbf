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
  globalThis.fixtureStepRunRoute = route
  globalThis.fixtureStepRunApi = new Proxy(api, {
    get: (target, key) => target[key] || (async () => ({}))
  })
  const source = await readFile(new URL('../src/views/EngagementDetailView.vue', import.meta.url), 'utf8')
  const { parse, compileScript } = await import('@vue/compiler-sfc')
  const { descriptor } = parse(source)
  let code = compileScript(descriptor, { id: 'engagement-playbook-step', inlineTemplate: true }).content
    .replace(/from ["']vue["']/g, `from ${JSON.stringify(vueUrl)}`)
    .replace("import { useRoute, useRouter } from 'vue-router'", "const useRoute = () => globalThis.fixtureStepRunRoute; const useRouter = () => ({ push() {} })")
    .replace("import { api } from '../api'", 'const api = globalThis.fixtureStepRunApi')
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

test('ejecutar un paso individual de un playbook llama a api.runPlaybookStep y actualiza el resultado', async () => {
  let stepRunCalled = false
  let stepPayload = null

  const mockDetail = {
    is_valid: true,
    errors: [],
    playbook: {
      id: 'pb_step_test',
      title: 'Playbook Test Step',
      version: '1.0',
      category: 'recon',
      steps: [
        {
          id: 'step_one',
          title: 'Primer Paso Test',
          interaction_type: 'passive',
          command_template: 'echo "hello"',
        }
      ]
    }
  }

  const apiMock = {
    getEngagement: async () => ({ id: 'test-proj', name: 'Test Proj', target: 'target.local' }),
    getPlaybooks: async () => [{ id: 'pb_step_test', title: 'Playbook Test Step', is_valid: true }],
    getPlaybook: async () => mockDetail,
    getPlaybookRuns: async () => [],
    validatePlaybook: async () => ({ is_valid: true, scope_evaluation: { can_execute: true } }),
    runPlaybookStep: async (id, payload) => {
      stepRunCalled = true
      stepPayload = payload
      return {
        playbook_id: id,
        step_id: payload.step_id,
        step_result: {
          step_id: payload.step_id,
          title: 'Primer Paso Test',
          status: 'SIMULATED',
          command: 'echo "hello"',
          exit_code: 0,
          output: '[dry-run] Simulación completada con éxito.'
        }
      }
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
    await clickText(root, 'Playbooks')

    // El playbook 'pb_step_test' se selecciona automáticamente al cargarse la lista
    await flush()

    const stepBtn = root.querySelector('[data-testid="run-playbook-step-btn"]')
    assert.ok(stepBtn, 'run-playbook-step-btn should be present')

    stepBtn.click()
    await flush()

    assert.equal(stepRunCalled, true)
    assert.equal(stepPayload.step_id, 'step_one')

    const statusBadge = root.querySelector('[data-testid="step-status-step_one"]')
    assert.ok(statusBadge, 'step-status-step_one badge should appear')
    assert.equal(statusBadge.textContent.trim(), 'SIMULATED')
  } finally {
    cleanup()
  }
})
