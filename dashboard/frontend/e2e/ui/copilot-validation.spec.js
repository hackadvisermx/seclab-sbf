import { test, expect } from '@playwright/test'

test('Copiloto comunica validación no disponible sin ejecutar acciones', async ({ page, baseURL }, testInfo) => {
  const writes = []
  let sentPayload = null
  const original = '<script>fixture-only</script> Revisa example.test.'
  const content = '⚠️ Validación de alcance no disponible. La comprobación de alcance agotó su tiempo de espera.\n'
    + 'Esta respuesta sigue siendo una sugerencia sin comprobación de alcance. Revisa y corrige el alcance antes de realizar acciones; el Copiloto no autoriza ni ejecuta pruebas.\n\n' + original
  await page.route('**/*', route => {
    const request = route.request()
    const url = new URL(request.url())
    if (url.origin !== baseURL) return route.abort()
    if (!url.pathname.startsWith('/api/')) return route.continue()
    if (request.method() !== 'GET') writes.push(url.pathname)
    if (url.pathname === '/api/v1/copilot/chat') sentPayload = request.postDataJSON()
    let data = {}
    if (url.pathname === '/api/v1/auth/me') data = { username: 'tester' }
    else if (url.pathname === '/api/v1/copilot/context/fixture') data = { context: '# Alcance\nPRIVATE-CONTEXT' }
    else if (url.pathname === '/api/v1/copilot/review') data = { context: '# Alcance\nPRIVATE-CONTEXT', context_review_token: 'fixture-review-token' }
    else if (url.pathname === '/api/v1/copilot/chat') data = { content, provider: 'fixture', model: 'fixture-model', latency_ms: 12 }
    else if (url.pathname === '/api/v1/vault' || url.pathname.startsWith('/api/v1/findings/') || url.pathname.startsWith('/api/v1/artifacts/')) data = []
    else if (url.pathname.includes('/loot/')) data = { credentials: [], files: [] }
    else if (url.pathname.endsWith('/history')) data = { jobs: [], next_cursor: null }
    else if (url.pathname.startsWith('/api/v1/recon/')) data = { job: { status: 'idle' }, summary: {}, configured_domains: [] }
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(data) })
  })
  await page.goto('/engagements/engagement/fixture')
  await page.getByRole('button', { name: /Copiloto Táctico/ }).click()
  await page.getByPlaceholder('Pregunta al copiloto sobre el alcance, metodología, o redacción de hallazgos...').fill('Ayuda con evidencia')
  await page.getByRole('button', { name: 'Revisar y enviar', exact: true }).click()
  await expect(page.getByRole('textbox', { name: 'Contexto revisado para enviar' })).toHaveValue('# Alcance\nPRIVATE-CONTEXT')
  expect(writes).toEqual(['/api/v1/copilot/review'])
  await page.getByRole('textbox', { name: 'Contexto revisado para enviar' }).fill('# Alcance\n[REDACTED]')
  await page.getByRole('textbox', { name: 'Mensaje revisado 1' }).fill('Pregunta redactada')
  await page.screenshot({ path: testInfo.outputPath('copilot-context-review.png') })
  await page.getByRole('button', { name: 'Enviar contenido revisado' }).click()
  const response = page.locator('pre').filter({ hasText: 'Validación de alcance no disponible' })
  await expect(response).toHaveText(content)
  await expect(page.getByText('COPILOTO (fixture-model)', { exact: true })).toBeVisible()
  await expect(page.locator('script').filter({ hasText: 'fixture-only' })).toHaveCount(0)
  expect(writes).toEqual(['/api/v1/copilot/review', '/api/v1/copilot/chat'])
  expect(sentPayload.reviewed_context).toBe('# Alcance\n[REDACTED]')
  expect(sentPayload.context_review_token).toBe('fixture-review-token')
  expect(sentPayload.source_messages).toEqual([{ role: 'user', content: 'Ayuda con evidencia' }])
  expect(sentPayload.reviewed_messages).toEqual([{ role: 'user', content: 'Pregunta redactada' }])
  await response.screenshot({ path: testInfo.outputPath('copilot-validation-unavailable.png') })
})
