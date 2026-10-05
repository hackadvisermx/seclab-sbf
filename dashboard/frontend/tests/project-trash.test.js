import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { createRequire } from 'node:module'
import { pathToFileURL } from 'node:url'
import { test } from 'node:test'
import { JSDOM } from 'jsdom'
import { parse, compileScript } from '@vue/compiler-sfc'

const browser = new JSDOM('<body></body>', { url: 'http://localhost' })
for (const name of ['window', 'document', 'Element', 'SVGElement', 'HTMLElement', 'Node']) globalThis[name] = browser.window[name]
const { createApp, nextTick } = await import('vue')
const vueUrl = pathToFileURL(createRequire(import.meta.url).resolve('vue/dist/vue.runtime.esm-bundler.js')).href

async function mountView(filename, api, props = {}) {
  globalThis.fixtureTrashApi = api
  const source = await readFile(new URL(`../src/${filename}`, import.meta.url), 'utf8')
  const { descriptor } = parse(source)
  const compiled = compileScript(descriptor, { id: filename, inlineTemplate: true })
  const code = compiled.content.replace(/from ["']vue["']/g, `from ${JSON.stringify(vueUrl)}`)
    .replace("import { api } from '../api'", 'const api = globalThis.fixtureTrashApi')
  const component = (await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}#${Math.random()}`)).default
  const root = document.createElement('div')
  document.body.append(root)
  const app = createApp(component, props)
  app.component('router-link', { props: ['to'], template: '<a :href="to"><slot /></a>' })
  app.mount(root)
  await flush()
  return { root, cleanup() { app.unmount(); root.remove() } }
}

async function flush() {
  await nextTick()
  await new Promise(resolve => setTimeout(resolve, 0))
  await nextTick()
}

const entry = { entry_id: 'fixture-entry', project_id: 'sample', type: 'reto', deleted_at: '2026-10-05T12:00:00+00:00' }

test('restaura una copia y ofrece abrir el proyecto conservando la otra versión', async () => {
  const other = { ...entry, entry_id: 'other-entry', deleted_at: '2026-10-04T12:00:00+00:00' }
  const calls = []
  const view = await mountView('views/TrashView.vue', {
    getTrash: async () => [entry, other], restoreProject: async value => calls.push(value),
  })
  try {
    assert.equal(view.root.querySelectorAll('article').length, 2)
    view.root.querySelector('article button').click()
    await flush()
    assert.equal(calls.length, 1)
    assert.equal(calls[0].entry_id, entry.entry_id)
    assert.equal(view.root.querySelectorAll('article').length, 1)
    assert.match(view.root.querySelector('[role="status"]').textContent, /Se restauró sample/)
    assert.equal(view.root.querySelector('[role="status"] a').getAttribute('href'), '/engagements/reto/sample')
  } finally { view.cleanup() }
})

test('un conflicto conserva la copia y permite volver a intentar restaurarla', async () => {
  const view = await mountView('views/TrashView.vue', {
    getTrash: async () => [entry], restoreProject: async () => { throw new Error('Ya existe un proyecto con ese nombre y tipo.') },
  })
  try {
    view.root.querySelector('article button').click()
    await flush()
    assert.equal(view.root.querySelectorAll('article').length, 1)
    assert.match(view.root.querySelector('[role="alert"]').textContent, /Ya existe un proyecto/)
    assert.equal(view.root.querySelector('article button').disabled, false)
    assert.equal(view.root.querySelector('[role="status"]'), null)
  } finally { view.cleanup() }
})

test('la confirmación de eliminación explica la recuperación y llama la API solo al confirmar', async () => {
  const calls = []
  const view = await mountView('components/DeleteProjectButton.vue', {
    deleteEngagement: async (...args) => calls.push(args),
  }, { projectId: 'sample', projectType: 'reto' })
  try {
    view.root.querySelector('button').click()
    await flush()
    const dialog = document.querySelector('[role="dialog"]')
    assert.match(dialog.textContent, /Podrás restaurarlo desde la papelera/)
    assert.equal(calls.length, 0)
    const confirm = Array.from(dialog.querySelectorAll('button')).find(button => button.textContent.includes('Mover a la papelera'))
    confirm.click()
    await flush()
    assert.deepEqual(calls, [['sample', 'reto']])
    assert.equal(document.querySelector('[role="dialog"]'), null)
  } finally { view.cleanup() }
})
