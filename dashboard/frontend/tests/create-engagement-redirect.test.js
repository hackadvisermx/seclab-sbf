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
// Debe resolver al MISMO fichero que el "await import('vue-router')" de
// arriba (ESM), no al entrypoint CJS que usaria require.resolve: si son
// ficheros distintos, cada uno crea su propio Symbol(router) interno y
// useRouter() dentro del componente nunca encuentra el router instalado
// con app.use(router) en el test.
const vueRouterUrl = import.meta.resolve('vue-router')

// Fase 109 / backlog A5: tras crear un proyecto, el dashboard debe llevar
// directo a su detalle en vez de volver a la lista.
async function mountView(filename, api) {
  globalThis.fixtureCreateApi = api
  const source = await readFile(new URL(`../src/${filename}`, import.meta.url), 'utf8')
  const { parse, compileScript } = await import('@vue/compiler-sfc')
  const { descriptor } = parse(source)
  const compiled = compileScript(descriptor, { id: filename, inlineTemplate: true })
  const code = compiled.content
    .replace(/from ["']vue["']/g, `from ${JSON.stringify(vueUrl)}`)
    .replace(/from ["']vue-router["']/g, `from ${JSON.stringify(vueRouterUrl)}`)
    .replace("import { api } from '../api'", 'const api = globalThis.fixtureCreateApi')
    .replace(
      /import DeleteProjectButton from ['"]\.\.\/components\/DeleteProjectButton\.vue['"]/,
      'const DeleteProjectButton = { props: ["projectId", "projectType"], emits: ["deleted"], template: "<button type=\\"button\\">Eliminar</button>" }'
    )
  const component = (await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}#${Math.random()}`)).default

  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/engagements', component: { template: '<div />' } },
      { path: '/engagements/:type/:id', component: { template: '<div id="detail-stub">detalle</div>' } },
    ],
  })
  await router.push('/engagements')
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

test('tras crear un engagement, redirige al detalle en vez de volver a la lista', async () => {
  const created = { id: 'acme-corp', name: 'acme-corp', type: 'engagement', path: '/workspace/engagements/acme-corp' }
  const view = await mountView('views/EngagementsView.vue', {
    getEngagements: async () => [],
    createEngagement: async () => created,
  })
  try {
    view.root.querySelector('button').click()
    await flush()
    const nameInput = view.root.querySelector('form input[type="text"]')
    nameInput.value = 'acme-corp'
    nameInput.dispatchEvent(new browser.window.Event('input'))
    await flush()
    view.root.querySelector('form').dispatchEvent(new browser.window.Event('submit', { bubbles: true, cancelable: true }))
    await flush()
    assert.equal(view.router.currentRoute.value.fullPath, '/engagements/engagement/acme-corp')
  } finally {
    view.cleanup()
  }
})

test('tras crear un reto, redirige al detalle del reto (no al de engagement)', async () => {
  const created = { id: 'htb-lame', name: 'htb-lame', type: 'reto', path: '/workspace/retos/htb-lame' }
  const view = await mountView('views/EngagementsView.vue', {
    getEngagements: async () => [],
    createEngagement: async () => created,
  })
  try {
    view.root.querySelector('button').click()
    await flush()
    const nameInput = view.root.querySelector('form input[type="text"]')
    nameInput.value = 'htb-lame'
    nameInput.dispatchEvent(new browser.window.Event('input'))
    await flush()
    view.root.querySelector('form').dispatchEvent(new browser.window.Event('submit', { bubbles: true, cancelable: true }))
    await flush()
    assert.equal(view.router.currentRoute.value.fullPath, '/engagements/reto/htb-lame')
  } finally {
    view.cleanup()
  }
})
