// @ts-check
const { defineConfig } = require('@playwright/test');

const port = process.env.PORT || '5001';
const baseURL = process.env.OIKONOMIA_URL || `http://127.0.0.1:${port}`;

module.exports = defineConfig({
  testDir: './tests',
  timeout: 60000,
  use: {
    baseURL,
    trace: 'on-first-retry',
  },
  projects: [
    { name: 'chromium', use: { browserName: 'chromium' } },
  ],
  webServer: process.env.PLAYWRIGHT_SKIP_SERVER
    ? undefined
    : {
        command: `${process.env.PYTHON || './venv/bin/python3'} app.py`,
        url: `${baseURL}/__e2e__/combat-v2`,
        timeout: 120000,
        reuseExistingServer: !process.env.CI,
        env: {
          ...process.env,
          PORT: port,
          COMBAT_V2: '1',
          COMBAT_E2E: '1',
          FLASK_ENV: 'development',
          SECRET_KEY: process.env.SECRET_KEY || 'test-secret-e2e',
        },
      },
});