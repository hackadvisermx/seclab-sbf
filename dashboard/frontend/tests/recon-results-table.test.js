import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { test } from 'node:test'

// Fase 118 / backlog A13: la pestaña Reconocimiento debe mostrar una tabla
// ordenable de recon/probe_observations.jsonl (ya normalizada en
// src/recon-results.js), en vez de obligar a descargar el .jsonl crudo
// desde Artefactos para ver el detalle por host.

test('EngagementDetailView importa y usa las utilidades de recon-results.js', async () => {
  const source = await readFile(new URL('../src/views/EngagementDetailView.vue', import.meta.url), 'utf8')
  assert.match(source, /import \{ normalizeProbeResults, sortProbeResults \} from '\.\.\/recon-results'/)
  assert.match(source, /sortedProbeResults = computed\(/, 'Las filas mostradas deben derivarse con un computed, no mutarse directamente')
  assert.match(source, /toggleProbeSort\(/, 'Debe existir una función para alternar la columna/dirección de orden')
  assert.match(source, /probe_results:\s*\[\],/, 'El estado inicial de reconStatus debe incluir probe_results')
})

test('no se afirma ni se muestra un titulo de pagina inexistente', async () => {
  const source = await readFile(new URL('../src/views/EngagementDetailView.vue', import.meta.url), 'utf8')
  const tableSection = source.slice(source.indexOf('Resultados del Sondeo por Host'), source.indexOf('Consola de Ejecución en Vivo'))
  assert.doesNotMatch(tableSection, />\s*Título\s*</i, 'No debe aparecer una columna de "Título": el sondeo no lee el cuerpo de la respuesta')
})
