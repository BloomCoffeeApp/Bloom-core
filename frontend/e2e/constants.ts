import path from 'node:path'

/** Ports of the isolated e2e stack (the dev servers use 47821 / 5173). */
export const API_PORT = 47899
export const WEB_PORT = 5199
export const API_URL = `http://127.0.0.1:${API_PORT}`

/** Logged-in admin session saved by global.setup.ts. */
export const ADMIN_STATE = path.join(import.meta.dirname, '.tmp', 'admin.json')

/** Fictitious users created by the first-time setup with demo data. */
export const ADMIN = { name: 'Admin', pin: '0000' }
export const USERS = {
  caja: { name: 'Caja Demo', pin: '1111' },
  barista: { name: 'Barista Demo', pin: '2222' },
  encargado: { name: 'Encargado Demo', pin: '3333' },
}

/** Fake machine id for the e2e backend (licenses are bound to it). */
export const E2E_MACHINE = 'e2e-machine'
