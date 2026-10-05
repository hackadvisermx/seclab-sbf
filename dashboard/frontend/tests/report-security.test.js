import assert from 'node:assert/strict'
import { test } from 'node:test'
import { JSDOM } from 'jsdom'

const browser = new JSDOM('')
globalThis.window = browser.window
const { renderReport } = await import('../src/report-security.js')

test('elimina scripts, handlers, enlaces javascript y SVG del reporte', () => {
  const result = renderReport('# Evidencia\n<script>alert(1)</script><img src="x" onerror="alert(1)"><a href="javascript:alert(1)">ver</a><svg onload="alert(1)"></svg>')
  const document = new JSDOM(result).window.document
  assert.equal(document.querySelectorAll('script,svg,[onerror],[onload],[href^="javascript:"]').length, 0)
  assert.equal(document.querySelector('h1').textContent, 'Evidencia')
})

test('preserva tablas, código HTTP y enlaces HTTPS', () => {
  const result = renderReport('|Activo|Estado|\n|---|---|\n|app|pendiente|\n\n```http\nGET / HTTP/1.1\n```\n\n[referencia](https://example.org)')
  const document = new JSDOM(result).window.document
  assert.ok(document.querySelector('table'))
  assert.match(document.querySelector('code').textContent, /GET \/ HTTP\/1.1/)
  assert.equal(document.querySelector('a').href, 'https://example.org/')
})
