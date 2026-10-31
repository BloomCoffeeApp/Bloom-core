import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

import { E2E_MACHINE } from './constants'

const brand = JSON.parse(fs.readFileSync(path.resolve(import.meta.dirname, '../../brand.json'), 'utf8'))

/** Same derivation as backend app/licensing/machine.py. */
const machineId = () =>
  crypto.createHash('sha256').update(`${brand.appId}:${E2E_MACHINE}`).digest('hex').slice(0, 32)

/** A perpetual Pro license signed with the run's throwaway key (see playwright.config.ts). */
export function e2eProLicense(overrides: Record<string, unknown> = {}) {
  const payload = {
    v: 1, lid: 'L-e2e', cust: 'E2E', plan: 'pro', features: ['*'], mid: machineId(),
    iat: Math.floor(Date.now() / 1000), exp: null, grace: 0, ...overrides,
  }
  const body = Buffer.from(JSON.stringify(payload)).toString('base64url')
  const key = crypto.createPrivateKey(process.env.BLOOM_E2E_LICENSE_KEY!)
  const sig = crypto.sign(null, Buffer.from(`BLOOM1.${body}`), key).toString('base64url')
  return `BLOOM1.${body}.${sig}`
}
