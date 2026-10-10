import { expect } from '@playwright/test'
import { readFile, writeFile, unlink } from 'node:fs/promises'

export async function verifyCopilotContextGate(page, testInfo, workspace) {
  const id = 'copilot-local'
  const path = `${workspace}/engagements/${id}/recon/live_hosts.txt`
  const original = await readFile(path).catch(error => { if (error.code === 'ENOENT') return null; throw error })
  const scope = await readFile(`${workspace}/engagements/${id}/target.yaml`)
  const history = await (await page.request.get(`/api/v1/recon/${id}/history`)).json()
  const job = (await (await page.request.get(`/api/v1/recon/${id}/status`)).json()).job
  try {
    await writeFile(path, Buffer.concat([Buffer.from([0xff]), Buffer.from('fixture-context-private')]))
    const preview = await page.request.get(`/api/v1/copilot/context/${id}?agent=general`)
    expect(preview.status()).toBe(503)
    expect((await preview.json()).detail).toContain('Contexto no disponible')
    expect(await preview.text()).not.toMatch(/fixture-context-private|Traceback|UnicodeDecodeError/)
    await page.getByRole('button', { name: /Copiloto Táctico/ }).click()
    await page.getByRole('button', { name: 'Ver Contexto pt-context', exact: true }).click()
    await expect(page.locator('pre').filter({ hasText: 'Error al cargar contexto: Contexto no disponible' })).toBeVisible()
    await page.screenshot({ path: testInfo.outputPath('copilot-context-unavailable.png'), fullPage: true })
    await page.getByRole('button', { name: 'Cerrar', exact: true }).click()
    await page.getByPlaceholder('Pregunta al copiloto sobre el alcance, metodología, o redacción de hallazgos...').fill('Ayuda con contexto indisponible')
    const failure = page.waitForResponse(response => response.url().includes('/copilot/chat'))
    await page.getByRole('button', { name: 'Enviar Consulta', exact: true }).click()
    expect((await failure).status()).toBe(503)
    await expect(page.locator('pre').filter({ hasText: '[Error del Copiloto]' }).last()).toContainText('Contexto no disponible')
    const card = page.getByTestId('copilot-local-guidance')
    await expect(card).toContainText(job.run_id)
    await expect(card.locator('code')).toHaveCount(0)
    await page.evaluate(() => window.scrollTo(0, 0))
    await page.screenshot({ path: testInfo.outputPath('copilot-context-local-fallback.png'), fullPage: true })
    expect(await readFile(`${workspace}/engagements/${id}/target.yaml`)).toEqual(scope)
    expect(await (await page.request.get(`/api/v1/recon/${id}/history`)).json()).toEqual(history)
    expect((await (await page.request.get(`/api/v1/recon/${id}/status`)).json()).job).toEqual(job)
  } finally {
    if (original === null) await unlink(path)
    else await writeFile(path, original)
  }
  const recovered = await page.request.get(`/api/v1/copilot/context/${id}?agent=general`)
  expect(recovered.status()).toBe(200)
  expect((await recovered.json()).context).toContain(job.run_id)
}
