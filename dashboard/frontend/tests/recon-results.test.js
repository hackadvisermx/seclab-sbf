import assert from 'node:assert/strict'
import { test } from 'node:test'

const { normalizeProbeRow, normalizeProbeResults, sortProbeResults } = await import('../src/recon-results.js')

// Fase 118 / backlog A13: la pestaña Reconocimiento solo mostraba contadores;
// para ver el detalle por host (codigo HTTP, direccion, estado) habia que
// descargar recon/probe_observations.jsonl crudo desde Artefactos. El sondeo
// (seclab_recon_probe.py) nunca lee el cuerpo de la respuesta, asi que no
// existe un "titulo" de pagina real que normalizar o mostrar.

test('normaliza una fila de respuesta exitosa extrayendo el esquema de la URL', () => {
  const row = normalizeProbeRow({ host: 'a.example.test', url: 'https://a.example.test', address: '10.0.0.1', status: 'response', http_status: 200, location: null })
  assert.deepEqual(row, { host: 'a.example.test', scheme: 'https', address: '10.0.0.1', httpStatus: 200, status: 'response', detail: null })
})

test('normaliza una fila bloqueada sin url/address/http_status', () => {
  const row = normalizeProbeRow({ host: 'b.example.test', status: 'blocked', reason: 'DNS contiene una direccion excluida.' })
  assert.deepEqual(row, { host: 'b.example.test', scheme: null, address: null, httpStatus: null, status: 'blocked', detail: 'DNS contiene una direccion excluida.' })
})

test('prefiere la redireccion (location) sobre el motivo cuando ambos existen', () => {
  const row = normalizeProbeRow({ host: 'c.example.test', url: 'http://c.example.test', status: 'response', http_status: 301, location: 'https://c.example.test/' })
  assert.equal(row.detail, 'https://c.example.test/')
})

test('fila sin objeto o sin campos no revienta y devuelve valores vacios', () => {
  assert.deepEqual(normalizeProbeRow({}), { host: '', scheme: null, address: null, httpStatus: null, status: '', detail: null })
  assert.deepEqual(normalizeProbeResults(undefined), [])
  assert.deepEqual(normalizeProbeResults(null), [])
})

test('normalizeProbeResults aplica normalizeProbeRow a cada elemento del arreglo', () => {
  const rows = normalizeProbeResults([
    { host: 'z.example.test', url: 'https://z.example.test', status: 'response', http_status: 200 },
    { host: 'a.example.test', status: 'dns_error', reason: 'No se pudo resolver el destino.' },
  ])
  assert.equal(rows.length, 2)
  assert.equal(rows[0].host, 'z.example.test')
  assert.equal(rows[1].status, 'dns_error')
})

test('sortProbeResults ordena alfabeticamente por host ascendente por defecto', () => {
  const rows = normalizeProbeResults([
    { host: 'zeta.example.test', status: 'response', http_status: 200 },
    { host: 'alpha.example.test', status: 'response', http_status: 200 },
  ])
  const sorted = sortProbeResults(rows, 'host', 'asc')
  assert.deepEqual(sorted.map(r => r.host), ['alpha.example.test', 'zeta.example.test'])
})

test('sortProbeResults invierte el orden con direction "desc"', () => {
  const rows = normalizeProbeResults([
    { host: 'alpha.example.test', status: 'response', http_status: 200 },
    { host: 'zeta.example.test', status: 'response', http_status: 404 },
  ])
  const sorted = sortProbeResults(rows, 'httpStatus', 'desc')
  assert.deepEqual(sorted.map(r => r.httpStatus), [404, 200])
})

test('sortProbeResults ordena numericamente httpStatus, no como texto, y manda null al inicio', () => {
  const rows = normalizeProbeResults([
    { host: 'a.example.test', status: 'response', http_status: 404 },
    { host: 'b.example.test', status: 'blocked' },
    { host: 'c.example.test', status: 'response', http_status: 80 },
  ])
  const sorted = sortProbeResults(rows, 'httpStatus', 'asc')
  assert.deepEqual(sorted.map(r => r.httpStatus), [null, 80, 404])
})

test('sortProbeResults no muta el arreglo original', () => {
  const rows = normalizeProbeResults([
    { host: 'zeta.example.test', status: 'response', http_status: 200 },
    { host: 'alpha.example.test', status: 'response', http_status: 200 },
  ])
  const original = [...rows]
  sortProbeResults(rows, 'host', 'asc')
  assert.deepEqual(rows, original)
})
