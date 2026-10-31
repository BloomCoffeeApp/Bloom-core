import crypto from 'node:crypto'
import fs from 'node:fs'
import http from 'node:http'
import path from 'node:path'

import type { Page } from '@playwright/test'

import { MANIFEST_PORT } from './constants'
import { expect, test } from './fixtures'

/**
 * In-app updates against a local manifest server (the e2e backend's BLOOM_UPDATE_MANIFEST points
 * here). Manifests are signed with the run's throwaway key, like the e2e licenses. The installer is
 * never downloaded nor run here: that part is covered by pytest.
 */
const brand = JSON.parse(fs.readFileSync(path.resolve(import.meta.dirname, '../../brand.json'), 'utf8'))
const CURRENT: string = brand.version
const NEWER = `${Number(CURRENT.split('.')[0]) + 1}.0.0`

function signedManifest(version: string, notes = '') {
  const fields = {
    notes,
    published_at: '2026-10-30T12:00:00Z',
    sha256: 'a'.repeat(64),
    size: 52_428_800,
    url: `http://127.0.0.1:${MANIFEST_PORT}/Bloom-Setup-${version}.exe`,
    version,
  } // keys sorted: same canonical JSON as backend app/services/updates.py
  const key = crypto.createPrivateKey(process.env.BLOOM_E2E_LICENSE_KEY!)
  const msg = Buffer.concat([Buffer.from('BLOOM-UPDATE1\n'), Buffer.from(JSON.stringify(fields))])
  return { ...fields, signature: crypto.sign(null, msg, key).toString('base64url') }
}

let manifest: object = signedManifest(CURRENT)
let server: http.Server

test.describe.serial('Actualizaciones', () => {
  test.beforeAll(async () => {
    server = http.createServer((req, res) => {
      if (req.url !== '/latest.json') return void res.writeHead(404).end()
      res.writeHead(200, { 'Content-Type': 'application/json' }).end(JSON.stringify(manifest))
    })
    await new Promise<void>((resolve) => server.listen(MANIFEST_PORT, '127.0.0.1', resolve))
  })

  test.afterAll(async () => {
    await new Promise((resolve) => server.close(resolve))
  })

  const panel = (page: Page) => page.getByTestId('updates-panel')
  async function checkNow(page: Page) {
    const btn = panel(page).getByRole('button', { name: 'Buscar actualizaciones' })
    await btn.click()
    await expect(btn).toBeEnabled()
  }

  test('shows "Estás al día" when the published version is the installed one', async ({ page }) => {
    manifest = signedManifest(CURRENT)
    await page.goto('/config?tab=acerca')
    await expect(page.getByText(`Versión ${CURRENT}`)).toBeVisible()
    await checkNow(page)
    await expect(panel(page)).toContainText('Estás al día')
    await expect(panel(page).getByRole('button', { name: 'Actualizar ahora' })).toHaveCount(0)
  })

  test('offers a newer signed version with its notes, a header badge and a confirm dialog', async ({ page }) => {
    manifest = signedManifest(NEWER, 'Arqueo más rápido.\nCorrecciones varias.')
    await page.goto('/config?tab=acerca')
    await checkNow(page)
    await expect(panel(page)).toContainText(`Nueva versión ${NEWER} disponible`)
    await expect(panel(page)).toContainText('Arqueo más rápido.')
    await expect(page.locator('header').getByRole('link', { name: /Nueva versión/ })).toBeVisible()

    await panel(page).getByRole('button', { name: 'Actualizar ahora' }).click()
    const dlg = page.getByRole('alertdialog')
    await expect(dlg).toContainText(`¿Actualizar a la versión ${NEWER}?`)
    await expect(dlg).toContainText('se va a cerrar y volver a abrir')
    await dlg.getByRole('button', { name: 'Cancelar' }).click() // never run an installer in e2e
    await expect(dlg).toBeHidden()
  })

  test('ignores a manifest with a bad signature', async ({ page }) => {
    manifest = { ...signedManifest(NEWER), notes: 'alterado' }
    await page.goto('/config?tab=acerca')
    await checkNow(page)
    await expect(panel(page)).toContainText('no tiene una firma válida')
  })

  test('back to up to date clears the header badge', async ({ page }) => {
    // Also leaves the shared backend clean for the specs that run after this one.
    manifest = signedManifest(CURRENT)
    await page.goto('/config?tab=acerca')
    await checkNow(page)
    await expect(panel(page)).toContainText('Estás al día')
    await expect(page.locator('header').getByRole('link', { name: /Nueva versión/ })).toHaveCount(0)
  })
})
