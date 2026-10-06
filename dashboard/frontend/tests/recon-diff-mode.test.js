import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { test } from 'node:test'

// Fase 116 / backlog A11: pt-recon-pipeline.py ahora escribe subdomains_new.txt y
// live_hosts_new.txt comparando contra el estado previo de subdomains.txt/live_hosts.txt,
// y summary.json expone subdomains_new_count / live_hosts_new_count. La pestaña de
// Reconocimiento debe mostrar ese delta junto a los contadores acumulados existentes.

test('las tarjetas de Subdominios y Servicios Web muestran los nuevos desde la última corrida', async () => {
  const source = await readFile(new URL('../src/views/EngagementDetailView.vue', import.meta.url), 'utf8')
  assert.match(
    source,
    /\(reconStatus\.summary\?\.subdomains_new_count \|\| 0\) > 0/,
    'La tarjeta de subdominios debe condicionar el badge de nuevos a subdomains_new_count'
  )
  assert.match(
    source,
    /\(reconStatus\.summary\?\.live_hosts_new_count \|\| 0\) > 0/,
    'La tarjeta de servicios web debe condicionar el badge de nuevos a live_hosts_new_count'
  )
  assert.match(source, /subdomains_new_count:\s*0,/, 'El estado inicial de reconStatus.summary debe incluir subdomains_new_count')
  assert.match(source, /live_hosts_new_count:\s*0,/, 'El estado inicial de reconStatus.summary debe incluir live_hosts_new_count')
})
