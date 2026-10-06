import assert from 'node:assert/strict'
import { test } from 'node:test'
import { api } from '../src/api.js'

test('el Chat muestra errores JSON y texto sin consumir dos veces la respuesta', async () => {
  const originalFetch = globalThis.fetch
  try {
    for (const [body, expected] of [
      [JSON.stringify({ detail: 'OpenRouter: saldo insuficiente' }), /saldo insuficiente/],
      ['Upstream temporalmente inaccesible', /temporalmente inaccesible/],
      ['', /HTTP 502/],
    ]) {
      globalThis.fetch = async () => new Response(body, { status: 502 })
      await assert.rejects(api.proxyChat([{ role: 'user', content: 'Hola' }], 'openrouter', 'vendor/model'), expected)
    }
  } finally { globalThis.fetch = originalFetch }
})
