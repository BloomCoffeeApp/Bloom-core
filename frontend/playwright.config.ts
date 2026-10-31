import crypto from 'node:crypto'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

import { defineConfig } from '@playwright/test'

import { ADMIN_STATE, API_PORT, E2E_MACHINE, WEB_PORT } from './e2e/constants'

/**
 * End-to-end suite: starts an ISOLATED stack (own backend port, own fresh SQLite DB in a temp
 * folder, own Vite port) so it never touches the dev database or servers already running.
 * Browser: the Microsoft Edge that ships with Windows (no Playwright browser download).
 */
const FRONTEND = import.meta.dirname
const BACKEND = path.resolve(FRONTEND, '../backend')

// Fresh data dir per run. Workers re-evaluate this file but inherit the env var, so they agree.
if (!process.env.BLOOM_E2E_DIR) {
  const tmp = os.tmpdir()
  for (const name of fs.readdirSync(tmp)) {
    if (!name.startsWith('bloom-e2e-')) continue
    try {
      fs.rmSync(path.join(tmp, name), { recursive: true, force: true })
    } catch {
      /* still in use by a previous run that didn't exit cleanly */
    }
  }
  process.env.BLOOM_E2E_DIR = fs.mkdtempSync(path.join(tmp, 'bloom-e2e-'))
}
const DATA_DIR = process.env.BLOOM_E2E_DIR
const PRO_LINK = path.join(FRONTEND, 'e2e', 'pro')
const PRO_E2E = fs.existsSync(PRO_LINK) ? fs.realpathSync(PRO_LINK) : null

// Throwaway license key pair: the setup project signs a Pro license the e2e backend accepts.
if (!process.env.BLOOM_E2E_LICENSE_KEY) {
  const { privateKey, publicKey } = crypto.generateKeyPairSync('ed25519')
  process.env.BLOOM_E2E_LICENSE_KEY = privateKey.export({ type: 'pkcs8', format: 'pem' }).toString()
  process.env.BLOOM_E2E_LICENSE_PUB = publicKey.export({ type: 'spki', format: 'der' }).subarray(-32).toString('base64url')
}
const python = path.join(BACKEND, '.venv', 'Scripts', process.platform === 'win32' ? 'python.exe' : 'python')

export default defineConfig({
  testDir: './e2e',
  outputDir: './test-results',
  fullyParallel: false,
  workers: 1, // one shared DB
  retries: process.env.CI ? 1 : 0,
  forbidOnly: !!process.env.CI,
  timeout: 45_000,
  expect: { timeout: 10_000 },
  reporter: [['list'], ['html', { open: 'never' }]],
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
  projects: [
    { name: 'setup', testMatch: /global\.setup\.ts/ },
    {
      name: 'e2e',
      dependencies: ['setup'],
      testIgnore: [/lockout\.spec\.ts/, /[\/]pro[\/]/],
      use: { storageState: ADMIN_STATE },
    },
    // Pro edition specs (private repo, linked as a junction that Playwright doesn't follow).
    ...(PRO_E2E
      ? [{ name: 'pro', testDir: PRO_E2E, dependencies: ['setup'], use: { storageState: ADMIN_STATE } }]
      : []),
    // Locks the login for every user from this device (per-IP throttle), so it runs last.
    { name: 'lockout', dependencies: PRO_E2E ? ['e2e', 'pro'] : ['e2e'], testMatch: /lockout\.spec\.ts/ },
  ],
  webServer: [
    {
      command: `"${python}" -m uvicorn app.main:app --host 127.0.0.1 --port ${API_PORT}`,
      cwd: BACKEND,
      url: `http://127.0.0.1:${API_PORT}/api/health`,
      env: {
        CAFE_DATA_DIR: DATA_DIR,
        CAFE_DB_PATH: path.join(DATA_DIR, 'e2e.db'),
        CAFE_PORT: String(API_PORT),
        BLOOM_LICENSE_PUBLIC_KEY: process.env.BLOOM_E2E_LICENSE_PUB!,
        BLOOM_MACHINE_ID: E2E_MACHINE,
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
      env: { CAFE_PORT: String(API_PORT), VITE_CACHE_DIR: 'node_modules/.vite-e2e' },
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
})
