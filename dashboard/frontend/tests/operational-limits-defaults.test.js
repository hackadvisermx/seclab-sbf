import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { test } from 'node:test'

// Fase 111 / backlog A7: cuando target.yaml no define operational_limits,
// el default real que aplica el backend (seclab_recon_probe.py /
// workspace-seed/templates/target.yaml) es 1 req/s y 1 hilo, no 20/5
// como mostraba la pestaña Alcance del dashboard.

test('la pestaña Alcance muestra los limites operacionales reales por defecto (1, no 20/5)', async () => {
  const source = await readFile(new URL('../src/views/EngagementDetailView.vue', import.meta.url), 'utf8')
  assert.match(
    source,
    /scopeData\.operational_limits\?\.max_requests_per_second \|\| 1\b/,
    'El fallback de peticiones/seg debe ser 1, el default real del backend'
  )
  assert.match(
    source,
    /scopeData\.operational_limits\?\.max_parallel_threads \|\| 1\b/,
    'El fallback de hilos concurrentes debe ser 1, el default real del backend'
  )
  assert.doesNotMatch(source, /max_requests_per_second \|\| 20\b/, 'No debe quedar el default erroneo de 20 req/s')
  assert.doesNotMatch(source, /max_parallel_threads \|\| 5\b/, 'No debe quedar el default erroneo de 5 hilos')
})
