import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { createRequire } from 'node:module'
import { pathToFileURL } from 'node:url'
import { test } from 'node:test'
import { JSDOM } from 'jsdom'
import { parse, compileScript } from '@vue/compiler-sfc'

const browser = new JSDOM('<body></body>', { url: 'http://localhost' })
for (const name of ['window', 'document', 'Element', 'SVGElement', 'HTMLElement', 'Node']) {
  globalThis[name] = browser.window[name]
}
const { createApp, nextTick, ref } = await import('vue')
const vueUrl = pathToFileURL(createRequire(import.meta.url).resolve('vue/dist/vue.runtime.esm-bundler.js')).href

async function mountNavbar(api) {
  globalThis.fixtureNavbarApi = api
  const source = await readFile(new URL('../src/components/Navbar.vue', import.meta.url), 'utf8')
  const { descriptor } = parse(source)
  const compiled = compileScript(descriptor, { id: 'Navbar.vue', inlineTemplate: true })
  const code = compiled.content
    .replace(/from ["']vue["']/g, `from ${JSON.stringify(vueUrl)}`)
    .replace("import { api } from '../api'", 'const api = globalThis.fixtureNavbarApi')
    .replace("import { useTheme } from '../theme'", 'const useTheme = () => ({ theme: { value: "dark" }, toggleTheme: () => {} })')

  const component = (await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}#${Math.random()}`)).default
  const root = document.createElement('div')
  document.body.append(root)
  const app = createApp(component)
  app.config.globalProperties.$route = { path: '/' }
  app.component('router-link', { props: ['to'], template: '<a :href="to"><slot /></a>' })
  app.mount(root)
  await flush()
  return { root, cleanup() { app.unmount(); root.remove() } }
}

async function flush() {
  await nextTick()
  await new Promise(resolve => setTimeout(resolve, 10))
  await nextTick()
}

test('Navbar muestra la IP Local (LAN) obtenida de la telemetría', async () => {
  const mockApi = {
    getTelemetry: async () => ({
      local_ip: '172.20.0.42',
      vpn: { connected: false, ip: null, profile: 'none', interface: 'tun0' },
      tailscale: { online: false, ip: null },
    }),
    getSavedVpnCredentials: async () => ({}),
  }

  const { root, cleanup } = await mountNavbar(mockApi)
  try {
    const text = root.textContent
    assert.match(text, /LOCAL:/)
    assert.match(text, /172\.20\.0\.42/)
  } finally {
    cleanup()
  }
})

test('Navbar muestra IP de VPN desconectada cuando la VPN está inactiva', async () => {
  const mockApi = {
    getTelemetry: async () => ({
      local_ip: '192.168.1.50',
      vpn: { connected: false, ip: null, profile: 'none', interface: 'tun0' },
      tailscale: { online: false, ip: null },
    }),
    getSavedVpnCredentials: async () => ({}),
  }

  const { root, cleanup } = await mountNavbar(mockApi)
  try {
    const text = root.textContent
    assert.match(text, /VPN:/)
    assert.match(text, /Desconectada/)
  } finally {
    cleanup()
  }
})

test('Navbar muestra la IP de VPN asignada y control de copiado cuando está conectada', async () => {
  const mockApi = {
    getTelemetry: async () => ({
      local_ip: '172.20.0.2',
      vpn: { connected: true, ip: '10.10.14.77', profile: 'tryhackme', interface: 'tun0' },
      tailscale: { online: false, ip: null },
    }),
    getSavedVpnCredentials: async () => ({}),
  }

  const { root, cleanup } = await mountNavbar(mockApi)
  try {
    const text = root.textContent
    assert.match(text, /10\.10\.14\.77/)
    assert.match(text, /THM/)
    const copyBtn = root.querySelector('button[title*="10.10.14.77"]')
    assert.ok(copyBtn, 'Debe existir un botón para copiar la IP de la VPN')
  } finally {
    cleanup()
  }
})
