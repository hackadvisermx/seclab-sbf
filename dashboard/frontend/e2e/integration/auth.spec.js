import { test, expect } from '@playwright/test'
import { readFile } from 'node:fs/promises'

test('usuario temporal inicia sesión y revoca su sesión al salir', async ({ page }) => {
  const user = JSON.parse(await readFile(new URL('../.playwright-fixture/user.json', import.meta.url), 'utf8'))
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'SecLab Dashboard' })).toBeVisible()
  await page.getByLabel('Contraseña').fill(user.password)
  await page.getByRole('button', { name: 'Entrar', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Cerrar sesión', exact: true })).toBeVisible()
  const me = await page.request.get('/api/v1/auth/me')
  expect(me.status()).toBe(200)
  expect((await me.json()).username).toBe(user.username)
  const cookies = await page.context().cookies()
  expect(cookies.find(cookie => cookie.name === 'seclab_session')?.httpOnly).toBe(true)
  await page.getByRole('button', { name: 'Cerrar sesión', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'SecLab Dashboard' })).toBeVisible()
  expect((await page.request.get('/api/v1/auth/me')).status()).toBe(401)
})
