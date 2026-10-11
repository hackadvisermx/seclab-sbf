import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { test } from 'node:test'

test('VaultView incluye badge de destino de red y advertencia de transporte inseguro', async () => {
  const source = await readFile(new URL('../src/views/VaultView.vue', import.meta.url), 'utf8')
  assert.match(source, /data-testid="destination-badge"/, 'Debe incluir data-testid para badge de destino')
  assert.match(source, /data-testid="insecure-transport-warning"/, 'Debe incluir advertencia de transporte inseguro')
  assert.match(source, /formatDestinationLabel/, 'Debe formatear la etiqueta del destino')
  assert.match(source, /getDestinationBadgeClass/, 'Debe estilizar el badge según la clasificación')
  assert.match(source, /LOCAL_LOOPBACK/, 'Debe contemplar loopback local')
  assert.match(source, /PRIVATE_NETWORK/, 'Debe contemplar red privada')
  assert.match(source, /PUBLIC_REMOTE/, 'Debe contemplar remoto público')
})

test('EngagementDetailView incluye bloque de información de destino y aviso de transporte en revisión', async () => {
  const source = await readFile(new URL('../src/views/EngagementDetailView.vue', import.meta.url), 'utf8')
  assert.match(source, /data-testid="destination-security-info"/, 'Debe incluir bloque de información de destino')
  assert.match(source, /data-testid="destination-transport-warning"/, 'Debe incluir aviso de transporte inseguro')
  assert.match(source, /destinationInfo/, 'Debe tener ref reactivo para la información de destino')
  assert.match(source, /res\.destination/, 'Debe capturar destination de la respuesta del backend')
  assert.match(source, /Remoto Público/, 'Debe advertir cuando el destino es público')
})
