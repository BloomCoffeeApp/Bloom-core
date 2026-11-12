import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

import { defineConfig } from '@playwright/test'

/**
 * Online demo mode (backend started with BLOOM_DEMO=1): isolated stack on its own ports and temp
 * folder. `npm run e2e:demo`. Ports: E2E_API_PORT / E2E_WEB_PORT (defaults 48071 / 5371).
 */
const FRONTEND = path.resolve(import.meta.dirname, '..')
const BACKEND = path.resolve(FRONTEND, '../backend')
const API_PORT = Number(process.env.E2E_API_PORT ?? 48071)
const WEB_PORT = Number(process.env.E2E_WEB_PORT ?? 5371)

if (!process.env.BLOOM_DEMO_E2E_DIR) process.env.BLOOM_DEMO_E2E_DIR = fs.mkdtempSync(path.join(os.tmpdir(), 'bloom-demo-e2e-'))
const DATA_DIR = process.env.BLOOM_DEMO_E2E_DIR
const python = path.join(BACKEND, '.venv', 'Scripts', process.platform === 'win32' ? 'python.exe' : 'python')

export default defineConfig({
  testDir: '.',
  outputDir: `../test-results/demo-${API_PORT}`,
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  timeout: 60_000,
  expect: { timeout: 15_000 },
  reporter: [['list']],
  use: {
    baseURL: `http://localhost:${WEB_PORT}`,
    channel: process.env.PW_CHANNEL ?? 'msedge',
    headless: true,
    locale: 'es-AR',
    timezoneId: 'America/Argentina/Buenos_Aires',
    viewport: { width: 1366, height: 820 },
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  webServer: [
    {
      command: `"${python}" -m uvicorn app.main:app --host 127.0.0.1 --port ${API_PORT}`,
      cwd: BACKEND,
      url: `http://127.0.0.1:${API_PORT}/api/health`,
      env: {
        BLOOM_DEMO: '1',
        BLOOM_DEMO_DIR: path.join(DATA_DIR, 'demo'),
        BLOOM_DEMO_SITE_URL: 'https://bloom.example.com',
        // Every test browser comes from 127.0.0.1: relax the per-IP caps (pytest covers them).
        BLOOM_DEMO_BURST_COUNT: '50',
        BLOOM_DEMO_NEW_PER_IP_DAY: '50',
        CAFE_DATA_DIR: DATA_DIR,
        CAFE_DB_PATH: path.join(DATA_DIR, 'unused.db'),
        CAFE_PORT: String(API_PORT),
        BLOOM_LICENSE_SERVER: '',
      },
      reuseExistingServer: false,
      timeout: 120_000,
      stdout: 'ignore',
      stderr: 'pipe',
    },
    {
      command: `npx vite --port ${WEB_PORT} --strictPort`,
      cwd: FRONTEND,
      url: `http://localhost:${WEB_PORT}`,
      env: { CAFE_PORT: String(API_PORT), VITE_CACHE_DIR: `node_modules/.vite-e2e-${WEB_PORT}` },
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
})
