import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { createRequire } from 'node:module'
import { pathToFileURL } from 'node:url'
import { test } from 'node:test'
import { JSDOM } from 'jsdom'

const browser = new JSDOM('<body></body>', { url: 'http://localhost' })
for (const name of ['window', 'document', 'Element', 'SVGElement', 'HTMLElement', 'Node', 'history', 'location']) globalThis[name] = browser.window[name]
const { createApp, nextTick } = await import('vue')
const { createRouter, createMemoryHistory } = await import('vue-router')
const require = createRequire(import.meta.url)
const vueUrl = pathToFileURL(require.resolve('vue/dist/vue.runtime.esm-bundler.js')).href
const vueRouterUrl = import.meta.resolve('vue-router')

// Fase 113 / backlog A9: el asistente guiado encadena crear proyecto,
// definir alcance y lanzar el primer recon en un solo flujo, en vez de
// obligar al operador a descubrir por su cuenta que son pasos separados.

async function mountWizard(api) {
  globalThis.fixtureWizardApi = api
  const source = await readFile(new URL('../src/views/NewAuditWizardView.vue', import.meta.url), 'utf8')
  const { parse, compileScript } = await import('@vue/compiler-sfc')
  const { descriptor } = parse(source)
  const compiled = compileScript(descriptor, { id: 'views/NewAuditWizardView.vue', inlineTemplate: true })
  const code = compiled.content
    .replace(/from ["']vue["']/g, `from ${JSON.stringify(vueUrl)}`)
    .replace(/from ["']vue-router["']/g, `from ${JSON.stringify(vueRouterUrl)}`)
    .replace("import { api } from '../api'", 'const api = globalThis.fixtureWizardApi')
    .replace(
      "import { splitIpsAndCidrs } from '../scope-utils'",
      `import { splitIpsAndCidrs } from ${JSON.stringify(new URL('../src/scope-utils.js', import.meta.url).href)}`
    )
    .replace(
      "import HelpTooltip from '../components/HelpTooltip.vue'",
      'const HelpTooltip = { props: ["label"], template: "<span><slot /></span>" }'
    )
  const component = (await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}#${Math.random()}`)).default

  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/wizard', component: { template: '<div />' } },
      { path: '/engagements/:type/:id', component: { template: '<div id="detail-stub">detalle</div>' } },
    ],
  })
  await router.push('/wizard')
  await router.isReady()

  const root = document.createElement('div')
  document.body.append(root)
  const app = createApp(component)
  app.use(router)
  app.component('router-link', { props: ['to'], template: '<a :href="to"><slot /></a>' })
  app.mount(root)
  await flush()
  return { root, router, cleanup() { app.unmount(); root.remove() } }
}

async function flush() {
  await nextTick()
  await new Promise(resolve => setTimeout(resolve, 0))
  await nextTick()
}

function setInputValue(input, value) {
  input.value = value
  input.dispatchEvent(new browser.window.Event('input'))
}

test('recorre los 3 pasos y termina en el detalle del proyecto creado', async () => {
  const calls = { createEngagement: null, updateScope: null, runRecon: null }
  const created = { id: 'acme-corp', name: 'acme-corp', type: 'engagement' }
  const view = await mountWizard({
    createEngagement: async (data) => { calls.createEngagement = data; return created },
    getScope: async () => ({ scope: { in_scope: { domains: [], ips: [], cidrs: [], endpoints: ['https://acme-corp.local/api'] }, out_of_scope: { domains: [], ips: [], cidrs: [], notes: [] } } }),
    updateScope: async (id, payload) => { calls.updateScope = { id, payload }; return { status: 'ok' } },
    runRecon: async (id, data, type) => { calls.runRecon = { id, data, type }; return { message: 'ok' } },
  })
  try {
    // Paso 1
    const nameInput = view.root.querySelector('input[type="text"]')
    setInputValue(nameInput, 'acme-corp')
    await flush()
    view.root.querySelector('button').click()
    await flush()
    assert.deepEqual(calls.createEngagement, { name: 'acme-corp', type: 'engagement', domain: '', client: '' })
    assert.match(view.root.textContent, /Paso 2/)

    // Paso 2: escribe un CIDR junto a una IP suelta para confirmar que se
    // clasifican por separado (reusa splitIpsAndCidrs, el fix de A1).
    const textareas = view.root.querySelectorAll('textarea')
    setInputValue(textareas[0], 'acme-corp.local')
    setInputValue(textareas[1], '10.0.0.5\n10.0.1.0/24')
    setInputValue(textareas[2], 'excluded.example.test')
    await flush()
    assert.equal(view.root.querySelector('button').disabled, true)
    const confirmation = view.root.querySelector('[data-testid="confirm-scope"]')
    confirmation.click()
    await flush()
    view.root.querySelector('button').click()
    await flush()
    assert.ok(calls.updateScope, 'debe llamar a updateScope')
    assert.deepEqual(calls.updateScope.payload.scope.in_scope.domains, ['acme-corp.local'])
    assert.deepEqual(calls.updateScope.payload.scope.in_scope.ips, ['10.0.0.5'])
    assert.deepEqual(calls.updateScope.payload.scope.in_scope.cidrs, ['10.0.1.0/24'])
    assert.deepEqual(calls.updateScope.payload.scope.out_of_scope.domains, ['excluded.example.test'])
    // El endpoint que ya existia en target.yaml debe conservarse, no perderse.
    assert.deepEqual(calls.updateScope.payload.scope.in_scope.endpoints, ['https://acme-corp.local/api'])
    assert.match(view.root.textContent, /Paso 3/)

    // Paso 3: lanza el recon en dry-run (checkbox activo por defecto) y
    // confirma la redireccion final al detalle real del proyecto.
    const checkbox = view.root.querySelector('input[type="checkbox"]')
    assert.equal(checkbox.checked, true, 'dry-run debe estar activo por defecto')
    checkbox.click()
    await flush()
    assert.equal(view.root.querySelector('button').disabled, true)
    assert.match(view.root.textContent, /autorización y vigencia/)
    checkbox.click()
    await flush()
    assert.equal(view.root.querySelector('button').disabled, false)
    view.root.querySelector('button').click()
    await flush()
    assert.deepEqual(calls.runRecon, { id: 'acme-corp', data: { stage: 'all', dry_run: true }, type: 'engagement' })
    assert.equal(view.router.currentRoute.value.fullPath, '/engagements/engagement/acme-corp')
  } finally {
    view.cleanup()
  }
})

test('omitir alcance y recon tambien termina en el detalle', async () => {
  const created = { id: 'htb-quick', name: 'htb-quick', type: 'engagement' }
  const view = await mountWizard({
    createEngagement: async () => created,
    getScope: async () => ({ scope: { in_scope: {}, out_of_scope: {} } }),
    updateScope: async () => { throw new Error('no deberia llamarse si se omite') },
    runRecon: async () => { throw new Error('no deberia llamarse si se omite') },
  })
  try {
    const nameInput = view.root.querySelector('input[type="text"]')
    setInputValue(nameInput, 'htb-quick')
    await flush()
    view.root.querySelector('button').click()
    await flush()
    assert.match(view.root.textContent, /Paso 2/)

    // Guardar sin confirmar abre el detalle y no permite lanzar el recon.
    view.root.querySelectorAll('button')[1].click()
    await flush()
    assert.equal(view.router.currentRoute.value.fullPath, '/engagements/engagement/htb-quick')
  } finally {
    view.cleanup()
  }
})

test('un error del backend en el paso 1 se muestra y no avanza de paso', async () => {
  const view = await mountWizard({
    createEngagement: async () => { throw new Error('Ya existe un proyecto con ese nombre.') },
  })
  try {
    const nameInput = view.root.querySelector('input[type="text"]')
    setInputValue(nameInput, 'acme-corp')
    await flush()
    view.root.querySelector('button').click()
    await flush()
    assert.match(view.root.textContent, /Ya existe un proyecto con ese nombre/)
    assert.match(view.root.textContent, /Paso 1/)
  } finally {
    view.cleanup()
  }
})

test('alcance vacío confirmado muestra un error y no avanza', async () => {
  let saves = 0
  const view = await mountWizard({ createEngagement: async () => ({ id: 'empty', type: 'engagement' }),
    getScope: async () => ({ scope: { in_scope: {}, out_of_scope: {} } }),
    updateScope: async () => { saves++ } })
  try {
    setInputValue(view.root.querySelector('input[type="text"]'), 'empty')
    await flush()
    view.root.querySelector('button').click(); await flush()
    view.root.querySelector('[data-testid="confirm-scope"]').click(); await flush()
    view.root.querySelector('button').click(); await flush()
    assert.match(view.root.textContent, /Indica al menos un dominio/)
    assert.equal(saves, 0)
    assert.match(view.root.textContent, /Paso 2/)
  } finally { view.cleanup() }
})
