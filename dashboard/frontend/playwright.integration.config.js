import { defineConfig } from '@playwright/test'
import config from './playwright.config.js'

export default defineConfig({
  ...config,
  testDir: './e2e/integration',
  retries: 0,
  webServer: {
    command: 'node e2e/temporary-backend.mjs',
    url: config.use.baseURL,
    reuseExistingServer: false,
    gracefulShutdown: { signal: 'SIGTERM', timeout: 10000 },
    timeout: 60000,
  },
})
