import { expect } from '@playwright/test'
import { writeFile } from 'node:fs/promises'

export async function verifyFindingStateParity(page, testInfo, workspace) {
  await page.route('**/*', route => new URL(route.request().url()).origin === 'http://127.0.0.1:4199' ? route.continue() : route.abort())
  const id = 'finding-state-parity'
  expect((await page.request.post('/api/v1/engagements', { data: { name: id, domain: 'example.test', type: 'engagement' } })).ok()).toBe(true)
  const scope = await (await page.request.get(`/api/v1/scope/${id}`)).json()
  scope.authorization = { reference: 'Fixture sin tráfico', valid_from: '2000-01-01T00:00:00Z',
    valid_until: '2099-01-01T00:00:00Z', allow_passive: true, allow_active: true }
  expect((await page.request.put(`/api/v1/scope/${id}`, { data: scope })).ok()).toBe(true)
  const root = `${workspace}/engagements/${id}`
  const initial = await (await page.request.get(`/api/v1/checklist/${id}`)).json()
  await writeFile(`${root}/notes.md`, initial.matrix.map(row => `## Disciplina: ${row.id}\n`).join(''))
  await writeFile(`${root}/REPORT.md`, 'Fixture report')
  await writeFile(`${root}/evidence/legacy.md`, '---\nid: LEGACY\ntitle: Señal sintética pendiente\n---\nstatus: PROVEN en el cuerpo no confirma la ficha')
  const checklist = await (await page.request.get(`/api/v1/checklist/${id}`)).json()
  expect(checklist.total_findings).toBe(1)
  expect(checklist.findings_summary).toMatchObject({ verified: 0, unverified: 1 })
  expect(checklist.readiness.ready_for_closure).toBe(false)
  expect(checklist.matrix.find(row => row.id === 'triage').status).toBe('IN_PROGRESS')
  expect((await (await page.request.get(`/api/v1/checklist/${id}/next`)).json()).next_step.id).toBe('verify_findings')
  await page.goto(`/engagements/engagement/${id}`)
  await page.getByRole('button', { name: /Metodología & Cobertura/ }).click()
  await expect(page.getByTestId('next-decision')).toContainText('Revisar Fichas Pendientes de Triaje')
  await page.reload()
  await page.getByRole('button', { name: /Metodología & Cobertura/ }).click()
  await expect(page.getByTestId('next-decision')).toContainText('Revisar Fichas Pendientes de Triaje')
  await page.getByRole('button', { name: /Copiloto Táctico/ }).click()
  await page.getByRole('button', { name: 'Ver Contexto pt-context', exact: true }).click()
  const context = page.locator('pre').filter({ hasText: 'Matriz de Hallazgos y Estados Declarados' })
  await expect(context).toContainText('`CANDIDATE`')
  await expect(context).toContainText('Requisitos de cierre pendientes')
  await page.screenshot({ path: testInfo.outputPath('finding-state-pending.png'), fullPage: true })
  await page.getByRole('button', { name: 'Cerrar', exact: true }).click()
  await writeFile(`${root}/evidence/legacy.md`, '---\nid: LEGACY\nstatus: DISPROVED\ntitle: Señal sintética descartada\n---\nRevisión explícita del fixture')
  await page.reload()
  await page.getByRole('button', { name: /Metodología & Cobertura/ }).click()
  const resolved = await (await page.request.get(`/api/v1/checklist/${id}`)).json()
  expect(resolved.findings_summary).toMatchObject({ verified: 0, unverified: 0, disproved: 1 })
  expect(resolved.readiness.ready_for_closure).toBe(true)
  await expect(page.getByTestId('next-decision')).toContainText('Generar Entrega Sanitizada y Sellar Engagement')
  await page.screenshot({ path: testInfo.outputPath('finding-state-resolved.png'), fullPage: true })
}
