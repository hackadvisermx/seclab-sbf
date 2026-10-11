import { expect } from '@playwright/test'
import { readFile, writeFile } from 'node:fs/promises'
import { createHash } from 'node:crypto'

export async function verifyFindingSourceErrors(page, testInfo, workspace) {
  const id = 'finding-version'
  const path = `${workspace}/engagements/${id}/evidence/broken.md`
  const scope = await readFile(`${workspace}/engagements/${id}/target.yaml`)
  const original = '---\ntitle: [\nstatus: PROVEN\n---\n<script>hostile()</script>\nFuente conservada'
  await writeFile(path, original)
  await page.reload()
  await page.getByRole('button', { name: /Hallazgos \(evidence\/\)/ }).click()
  await expect(page.getByTestId('finding-source-error')).toContainText('Metadata inválida')
  await expect(page.getByRole('button', { name: 'Editar', exact: true })).toBeDisabled()
  await expect(page.getByRole('button', { name: 'Eliminar', exact: true })).toBeDisabled()
  await expect(page.getByRole('heading', { name: 'broken.md', exact: true })).toBeVisible()
  const current = await (await page.request.get(`/api/v1/findings/${id}/broken`)).json()
  expect(current.frontmatter.status).toBe('BLOCKED')
  expect(current.source_sha256).toBe(createHash('sha256').update(original).digest('hex'))
  expect(current.body).toBe(original)
  expect((await page.request.post(`/api/v1/findings/${id}`, { data: { slug: 'broken', title: 'Overwrite', body: 'Lost', expected_source_sha256: current.source_sha256 } })).status()).toBe(409)
  expect(await readFile(path, 'utf8')).toBe(original)
  await page.screenshot({ path: testInfo.outputPath('finding-source-invalid.png'), fullPage: true })
  await page.getByRole('button', { name: 'Revisar fuente original', exact: true }).click()
  await expect(page.locator('pre').filter({ hasText: 'Fuente conservada' })).toContainText(original)
  expect(await page.locator('script').filter({ hasText: 'hostile()' }).count()).toBe(0)
  expect(await readFile(path, 'utf8')).toBe(original)
  await page.screenshot({ path: testInfo.outputPath('finding-source-original.png'), fullPage: true })
  await page.getByRole('button', { name: /Hallazgos \(evidence\/\)/ }).click()
  const repaired = '---\ntitle: Fuente reparada\nstatus: CANDIDATE\n---\nFuente conservada'
  await writeFile(path, repaired)
  await page.getByRole('button', { name: 'Recargar fichas tras revisar la fuente', exact: true }).click()
  await expect(page.getByTestId('finding-source-error')).toHaveCount(0)
  await page.getByRole('button', { name: 'Editar', exact: true }).click()
  await expect(page.getByTestId('finding-markdown')).toHaveValue('Fuente conservada')
  const saved = page.waitForResponse(r => r.url().includes(`/findings/${id}`) && r.request().method() === 'POST')
  await page.getByRole('button', { name: 'Guardar Ficha', exact: true }).click()
  expect((await saved).status()).toBe(200)
  await expect(page.getByRole('heading', { name: 'Fuente reparada', exact: true })).toBeVisible()
  const final = await (await page.request.get(`/api/v1/findings/${id}/broken`)).json()
  expect(final.source_error).toBeNull()
  expect(final.finding_id).toMatch(/^[a-f0-9]{32}$/)
  expect(final.body).toBe('Fuente conservada')
  expect(await readFile(`${workspace}/engagements/${id}/target.yaml`)).toEqual(scope)
  expect((await (await page.request.get(`/api/v1/recon/${id}/history`)).json()).jobs).toEqual([])
}
