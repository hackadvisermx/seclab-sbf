import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { test } from 'node:test'

// Fase 128 / backlog A21 (Tier 5, última acción): hoy la respuesta del
// Copiloto se muestra como texto plano sin aclarar que es solo una
// sugerencia. Un aviso corto y permanente evita que un operador sin
// experiencia asuma que el sistema ya ejecutó algo por él.

async function readCopilotTabSource() {
  const source = await readFile(new URL('../src/views/EngagementDetailView.vue', import.meta.url), 'utf8')
  const start = source.indexOf(`<div v-if="activeTab === 'copilot'"`)
  assert.notEqual(start, -1, 'No se encontró el bloque de la pestaña Copiloto')
  // La siguiente pestaña en el archivo marca el fin de este bloque.
  const end = source.indexOf('<!-- TAB', start + 1)
  return source.slice(start, end === -1 ? source.length : end)
}

test('la pestaña Copiloto tiene un aviso permanente de que solo sugiere, nunca ejecuta', async () => {
  const section = await readCopilotTabSource()
  assert.match(section, /únicamente.*sugiere/i)
  assert.match(section, /no ejecuta comandos/i)
})

test('el aviso no depende de v-if sobre el historial de mensajes (es permanente, no solo del estado vacío)', async () => {
  const section = await readCopilotTabSource()
  const noticeIndex = section.search(/no ejecuta comandos/i)
  assert.notEqual(noticeIndex, -1)
  // Retrocede hasta la apertura del div más cercano y confirma que no lleva
  // un v-if ligado a copilotMessages (a diferencia del estado vacío del chat,
  // que sí depende de v-if="copilotMessages.length === 0").
  const divStart = section.lastIndexOf('<div', noticeIndex)
  const divOpenTag = section.slice(divStart, section.indexOf('>', divStart) + 1)
  assert.doesNotMatch(divOpenTag, /v-if/, 'El aviso debe mostrarse siempre, no solo condicionalmente')
})
