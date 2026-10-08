import { defineConfig, devices } from '@playwright/test'

const baseURL = 'http://127.0.0.1:4199'

export default defineConfig({
  testDir: './e2e/ui',
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL,
    serviceWorkers: 'block',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: 'npm run build && npm run preview -- --host 127.0.0.1 --port 4199 --strictPort',
    url: baseURL,
    reuseExistingServer: false,
    timeout: 60000,
  },
})
