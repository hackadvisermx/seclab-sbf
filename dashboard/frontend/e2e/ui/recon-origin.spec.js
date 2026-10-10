import { test, expect } from '@playwright/test'

test('historial muestra etapas recuperadas y origen desconocido sin lanzar acciones', async ({ page, baseURL }, testInfo) => {
  const writes = []
  const snapshot = (origin, runId) => ({ schema_version: 2, recorded_at: '2026-10-10T12:00:00Z', metrics_source: 'previous_artifacts',
    metrics: { subdomains_count: 1, live_hosts_count: 0, urls_count: 0, js_files_count: 0 }, stages: [
      { stage: 'subdomains', status: 'completed', execution: 'recovered', origin_run_id: origin, counts: { in_scope_count: 1 }, patterns: {} },
      { stage: 'probe', status: 'failed', execution: 'current', origin_run_id: runId, counts: {}, patterns: {}, failure_kind: 'technical' },
    ] })
  const jobs = ['b', 'c'].map((letter, index) => ({ run_id: letter.repeat(32), status: 'failed', stage: 'all',
    started_at: '2026-10-10T12:00:00Z', finished_at: '2026-10-10T12:01:00Z', scope_revision: 'd'.repeat(64),
    result_summary: snapshot(index ? null : 'a'.repeat(32), letter.repeat(32)) }))
  await page.route('**/*', route => {
    const request = route.request(), url = new URL(request.url())
    if (url.origin !== baseURL) return route.abort()
    if (!url.pathname.startsWith('/api/')) return route.continue()
    if (request.method() !== 'GET') writes.push(url.pathname)
    let data = {}
    if (url.pathname === '/api/v1/auth/me') data = { username: 'tester' }
    else if (url.pathname === '/api/v1/vault' || url.pathname.startsWith('/api/v1/findings/') || url.pathname.startsWith('/api/v1/artifacts/')) data = []
    else if (url.pathname.includes('/loot/')) data = { credentials: [], files: [] }
    else if (url.pathname.endsWith('/history')) data = { jobs, next_cursor: null }
    else if (url.pathname.startsWith('/api/v1/recon/')) data = { job: { status: 'idle' }, summary: {}, configured_domains: [] }
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(data) })
  })
  await page.goto('/engagements/engagement/fixture')
  await page.getByRole('button', { name: /Reconocimiento/ }).filter({ hasText: '📡' }).click()
  const history = page.getByTestId('recon-history')
  const rows = history.getByRole('listitem')
  for (const row of await rows.all()) await row.getByText('Resultados conservados al terminar', { exact: true }).click()
  await expect(rows.nth(0)).toContainText('Run de origen: ' + 'a'.repeat(32))
  await expect(rows.nth(0)).toContainText('Intentada en este job')
  await expect(rows.nth(1)).toContainText('Run de origen: No registrado')
  await expect(history).toContainText('no se ejecutó en este job')
  expect(writes).toEqual([])
  await history.screenshot({ path: testInfo.outputPath('recovered-origin.png') })
})
