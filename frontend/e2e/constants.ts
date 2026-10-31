import path from 'node:path'

/** Ports of the isolated e2e stack (the dev servers use 47821 / 5173). Overridable so two suites can
 * run side by side: E2E_API_PORT / E2E_WEB_PORT. */
export const API_PORT = Number(process.env.E2E_API_PORT ?? 47899)
export const WEB_PORT = Number(process.env.E2E_WEB_PORT ?? 5199)
export const API_URL = `http://127.0.0.1:${API_PORT}`

/** Local server for the in-app update manifest (updates.spec.ts starts it; the backend points at it). */
export const MANIFEST_PORT = Number(process.env.E2E_MANIFEST_PORT ?? API_PORT + 2)

/** Logged-in admin session saved by global.setup.ts. */
export const ADMIN_STATE = path.join(import.meta.dirname, '.tmp', `admin-${API_PORT}.json`)

/** Fictitious users created by the first-time setup with demo data. */
export const ADMIN = { name: 'Admin', pin: '0000' }
export const USERS = {
  caja: { name: 'Caja Demo', pin: '1111' },
  barista: { name: 'Barista Demo', pin: '2222' },
  encargado: { name: 'Encargado Demo', pin: '3333' },
}

/** Fake machine id for the e2e backend (licenses are bound to it). */
export const E2E_MACHINE = 'e2e-machine'
