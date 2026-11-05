import fs from 'node:fs'
import path from 'node:path'

import type { Page } from '@playwright/test'

import { expect, test } from './fixtures'
import { openPos, productTile, withFreePlan } from './helpers'

/** Optional review screenshots (light + dark): BLOOM_SHOTS=<folder> npm run e2e. */
async function shots(page: Page, name: string) {
  const dir = process.env.BLOOM_SHOTS
  if (!dir) return
  fs.mkdirSync(dir, { recursive: true })
  for (const scheme of ['light', 'dark'] as const) {
    await page.emulateMedia({ colorScheme: scheme })
    await page.waitForTimeout(150)
    await page.screenshot({ path: path.join(dir, `${name}-${scheme}.png`), fullPage: false })
  }
  await page.emulateMedia({ colorScheme: 'light' })
}

test('free plan: locked items keep showing with a lock, the owner picks the actives and the POS sells only those', async ({ page, request }) => {
  await withFreePlan(page, request, async () => {
    // Everything stays visible: locked products carry the badge, and a banner explains it
    await page.goto('/productos')
    await expect(page.getByTestId('free-locks-banner')).toContainText('productos bloqueados')
    await expect(page.getByTestId('lock-badge').first()).toBeVisible()
    await shots(page, 'free-products-locked')

    // Elegí tus activos: 5 products active by default (the oldest)
    await page.goto('/config?tab=activos')
    const chooser = page.getByTestId('free-actives')
    await expect(chooser.getByRole('heading', { name: 'Elegí tus activos' }).or(chooser.getByText('Elegí tus activos').first())).toBeVisible()
    await expect(page.getByTestId('free-count')).toHaveText('5/5')
    await shots(page, 'free-elegi-tus-activos')

    // Swap: take Cortado out, put Latte in (first swap: no wait)
    const item = (name: string) => chooser.getByRole('checkbox', { name: new RegExp(`^${name}\\b`) })
    await expect(item('Cortado')).toHaveAttribute('aria-checked', 'true')
    await expect(item('Latte')).toBeDisabled() // at the cap
    await item('Cortado').click()
    await item('Latte').click()
    await expect(page.getByText('Sacar un activo cuenta como cambio')).toBeVisible()
    await page.getByRole('button', { name: 'Guardar activos' }).click()
    await expect(page.getByText('Listo: tus activos quedaron guardados.')).toBeVisible()
    await expect(page.getByText(/Próximo cambio por uno bloqueado/)).toBeVisible()
    await shots(page, 'free-elegi-tus-activos-cooldown')

    // The POS only offers the active ones
    await openPos(page)
    await expect(productTile(page, 'Latte')).toBeVisible()
    await expect(productTile(page, 'Espresso')).toBeVisible()
    await expect(page.getByRole('button', { name: /^Cortado\s*\$/ })).toHaveCount(0)
    await expect(page.getByRole('button', { name: /^Medialuna\s*\$/ })).toHaveCount(0)
    await shots(page, 'free-pos-only-actives')

    // A locked customer is shown but can't be picked for a sale
    await page.goto('/clientes')
    await expect(page.getByRole('heading', { name: 'Clientes' }).first()).toBeVisible()
  })
  // Back to Pro: everything unlocked again
  await openPos(page)
  await expect(productTile(page, 'Cortado')).toBeVisible()
  await expect(productTile(page, 'Medialuna')).toBeVisible()
})
