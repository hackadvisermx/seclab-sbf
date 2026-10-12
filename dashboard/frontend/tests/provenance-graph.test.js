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

globalThis.URL.createObjectURL = () => 'blob:mock-url'
globalThis.URL.revokeObjectURL = () => {}

const { createApp, nextTick } = await import('vue')
const require = createRequire(import.meta.url)
const vueUrl = pathToFileURL(require.resolve('vue/dist/vue.runtime.esm-bundler.js')).href

async function flush() {
  await nextTick()
  await new Promise(r => setTimeout(r, 0))
  await nextTick()
}

async function mount(api, route = { params: { id: 'test-proj', type: 'engagement' } }) {
  globalThis.fixtureProvRoute = route
  globalThis.fixtureProvApi = new Proxy(api, {
    get: (target, key) => target[key] || (async () => ({}))
  })
  const source = await readFile(new URL('../src/views/EngagementDetailView.vue', import.meta.url), 'utf8')
  const { parse, compileScript } = await import('@vue/compiler-sfc')
  const { descriptor } = parse(source)
  let code = compileScript(descriptor, { id: 'engagement-provenance-graph', inlineTemplate: true }).content
    .replace(/from ["']vue["']/g, `from ${JSON.stringify(vueUrl)}`)
    .replace("import { useRoute, useRouter } from 'vue-router'", "const useRoute = () => globalThis.fixtureProvRoute; const useRouter = () => ({ push() {} })")
    .replace("import { api } from '../api'", 'const api = globalThis.fixtureProvApi')
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

test('pestaña Línea de Tiempo renderiza el grafo estructurado de procedencia (DAG) (V3-02s)', async () => {
  let exportProvCalled = false
  let exportProvFormat = null

  const mockGraph = {
    engagement_id: 'test-proj',
    summary: {
      total_nodes: 5,
      total_edges: 4,
      provenance_coverage_pct: 100,
      findings_count: 1,
      with_provenance_count: 1,
      unlinked_findings_count: 0,
      complete_chains_count: 1,
    },
    nodes: [
      {
        id: 'scope:root',
        type: 'scope',
        label: 'Alcance (test-proj)',
        status: 'active',
        details: { targets_count: 1 },
      },
      {
        id: 'job:1',
        type: 'job',
        label: 'nmap (port_scan) #1',
        status: 'completed',
        details: { job_id: '1', tool: 'nmap' },
      },
      {
        id: 'finding:sqli',
        type: 'finding',
        label: '[HIGH] SQL Injection',
        status: 'PROVEN',
        details: { slug: 'sqli', source_job_id: '1' },
      },
      {
        id: 'deliverable:report',
        type: 'deliverable',
        label: 'Reporte (REPORT.md)',
        status: 'compiled',
        details: { file: 'REPORT.md' },
      },
    ],
    edges: [
      { id: 'e1', source: 'scope:root', target: 'job:1', type: 'targets', label: 'ejecuta en alcance' },
      { id: 'e2', source: 'job:1', target: 'finding:sqli', type: 'evidences', label: 'produce evidencia' },
      { id: 'e3', source: 'finding:sqli', target: 'deliverable:report', type: 'compiled_in', label: 'incluido en informe' },
    ],
  }

  const apiMock = {
    getEngagement: async () => ({ id: 'test-proj', name: 'Test Proj', target: 'target.local' }),
    getEngagementTimeline: async () => ({ events: [] }),
    getProvenanceGraph: async () => mockGraph,
    exportProvenanceGraph: async (id, format, type) => {
      exportProvCalled = true
      exportProvFormat = format
      return 'flowchart LR\n  sub_scope --> sub_job'
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
    // Cambiar a pestaña Línea de Tiempo
    await clickText(root, 'Línea de Tiempo')

    const provGraphCard = root.querySelector('[data-testid="provenance-flow-graph"]')
    assert.ok(provGraphCard, 'provenance-flow-graph card should be rendered')

    const totalNodesEl = root.querySelector('[data-testid="provenance-total-nodes"]')
    assert.ok(totalNodesEl, 'provenance-total-nodes should exist')
    assert.equal(totalNodesEl.textContent.trim(), '5')

    const coverageBadge = root.querySelector('[data-testid="provenance-coverage-badge"]')
    assert.ok(coverageBadge, 'provenance-coverage-badge should exist')
    assert.equal(coverageBadge.textContent.trim(), '100% Trazable')

    const exportMermaidBtn = root.querySelector('[data-testid="provenance-export-mermaid-btn"]')
    assert.ok(exportMermaidBtn, 'provenance-export-mermaid-btn should exist')

    exportMermaidBtn.click()
    await flush()

    assert.equal(exportProvCalled, true)
    assert.equal(exportProvFormat, 'mermaid')
  } finally {
    cleanup()
  }
})
