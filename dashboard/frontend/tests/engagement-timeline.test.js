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
  globalThis.fixtureTimelineRoute = route
  globalThis.fixtureTimelineApi = new Proxy(api, {
    get: (target, key) => target[key] || (async () => ({}))
  })
  const source = await readFile(new URL('../src/views/EngagementDetailView.vue', import.meta.url), 'utf8')
  const { parse, compileScript } = await import('@vue/compiler-sfc')
  const { descriptor } = parse(source)
  let code = compileScript(descriptor, { id: 'engagement-timeline', inlineTemplate: true }).content
    .replace(/from ["']vue["']/g, `from ${JSON.stringify(vueUrl)}`)
    .replace("import { useRoute, useRouter } from 'vue-router'", "const useRoute = () => globalThis.fixtureTimelineRoute; const useRouter = () => ({ push() {} })")
    .replace("import { api } from '../api'", 'const api = globalThis.fixtureTimelineApi')
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

const mockTimelineEvents = [
  {
    id: 'scope-test-proj',
    timestamp: '2026-10-11T10:00:00Z',
    category: 'scope',
    type: 'scope_configured',
    title: 'Alcance Autorizado (target.yaml)',
    status: 'info',
    summary: 'Alcance declarado con 1 dominio(s) y 0 IP(s).',
    source_ref: 'target.yaml',
    details: { version: '1.0' }
  },
  {
    id: 'job-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
    timestamp: '2026-10-11T10:05:00Z',
    category: 'recon',
    type: 'recon_job',
    title: 'Ejecución de Reconocimiento [probe]',
    status: 'success',
    summary: 'Job aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa (completed) en etapa probe',
    source_ref: 'recon/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
    details: { stage: 'probe', status: 'completed' }
  },
  {
    id: 'finding-sqli-test',
    timestamp: '2026-10-11T10:10:00Z',
    category: 'finding',
    type: 'finding_recorded',
    title: 'Hallazgo: Inyección SQL',
    status: 'error',
    summary: '[CRITICAL] Estado: CANDIDATE | Activo: example.test',
    source_ref: 'evidence/sqli-test.md',
    details: { severity: 'CRITICAL', status: 'CANDIDATE' }
  }
]

test('la pestaña Línea de Tiempo carga y renderiza eventos unificados', async () => {
  let timelineCalled = false
  const api = {
    getEngagementTimeline: async (id, type) => {
      timelineCalled = true
      return {
        engagement_id: id,
        type,
        total_events: mockTimelineEvents.length,
        events: mockTimelineEvents
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
    getReconHistory: async () => ({ jobs: [] }),
  }

  const view = await mount(api)
  try {
    assert.ok(timelineCalled, 'getEngagementTimeline debió llamarse al montar')
    // Cambiar a la pestaña Línea de Tiempo
    await clickText(view.root, 'Línea de Tiempo')

    const timelineContainer = view.root.querySelector('[data-testid="engagement-timeline-view"]')
    assert.ok(timelineContainer, 'Debe renderizarse el contenedor de línea de tiempo')

    const eventsList = view.root.querySelector('[data-testid="timeline-events-list"]')
    assert.ok(eventsList, 'Debe renderizarse la lista de eventos')

    const items = view.root.querySelectorAll('[data-testid="timeline-event-item"]')
    assert.equal(items.length, 3, 'Deben renderizarse los 3 eventos mockeados')

    // Verificar contenido de eventos
    assert.match(timelineContainer.textContent, /Alcance Autorizado/)
    assert.match(timelineContainer.textContent, /Ejecución de Reconocimiento/)
    assert.match(timelineContainer.textContent, /Hallazgo: Inyección SQL/)
  } finally {
    view.cleanup()
  }
})

test('el filtro de categoría en la línea de tiempo reduce los eventos mostrados', async () => {
  const api = {
    getEngagementTimeline: async (id, type) => ({
      engagement_id: id,
      type,
      total_events: mockTimelineEvents.length,
      events: mockTimelineEvents
    }),
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
  }

  const view = await mount(api)
  try {
    await clickText(view.root, 'Línea de Tiempo')

    // Filtrar por 'Hallazgos'
    const findingFilter = view.root.querySelector('[data-testid="timeline-filter-finding"]')
    assert.ok(findingFilter, 'Debe existir el botón de filtro de hallazgos')
    findingFilter.click()
    await flush()

    let items = view.root.querySelectorAll('[data-testid="timeline-event-item"]')
    assert.equal(items.length, 1, 'Solo debe haber 1 evento de hallazgo')
    assert.match(items[0].textContent, /Inyección SQL/)

    // Filtrar por 'Notas' (sin eventos)
    const notesFilter = view.root.querySelector('[data-testid="timeline-filter-notes"]')
    assert.ok(notesFilter, 'Debe existir el botón de filtro de notas')
    notesFilter.click()
    await flush()

    items = view.root.querySelectorAll('[data-testid="timeline-event-item"]')
    assert.equal(items.length, 0, 'No debe haber eventos de notas')

    const emptyState = view.root.querySelector('[data-testid="timeline-empty-state"]')
    assert.ok(emptyState, 'Debe mostrar el mensaje de estado vacío')
  } finally {
    view.cleanup()
  }
})
