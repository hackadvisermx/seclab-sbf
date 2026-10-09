import { test, expect } from '@playwright/test'

test.beforeEach(async ({ page, baseURL }) => {
  await page.route('**/*', route => {
    const url = new URL(route.request().url())
    if (url.origin !== baseURL) return route.abort()
    if (url.pathname.startsWith('/api/')) return route.fulfill({
      status: 401,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'Credenciales de prueba rechazadas' }),
    })
    return route.continue()
  })
})

test('muestra acceso privado y comunica el rechazo del login', async ({ page }) => {
  await page.goto('/engagements/engagement/fixture')
  await expect(page.getByRole('heading', { name: 'SecLab Dashboard' })).toBeVisible()
  await expect(page.getByLabel('Usuario')).toHaveValue('tester')
  await expect(page.getByLabel('Usuario')).toHaveAttribute('readonly', '')
  await page.getByLabel('Contraseña').fill('playwright-fixture-only')
  await page.getByRole('button', { name: 'Entrar', exact: true }).click()
  await expect(page.getByRole('alert')).toHaveText('Credenciales de prueba rechazadas')
  await expect(page.getByRole('button', { name: 'Entrar', exact: true })).toBeEnabled()
  await expect(page.getByRole('heading', { name: 'SecLab Dashboard' })).toBeVisible()
})

test('conserva el tema claro al recargar el formulario', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Modo Claro', exact: false }).click()
  await expect(page.locator('html')).toHaveClass(/light/)
  await page.reload()
  await expect(page.locator('html')).toHaveClass(/light/)
  await expect(page.getByRole('button', { name: 'Modo Oscuro', exact: false })).toBeVisible()
})
