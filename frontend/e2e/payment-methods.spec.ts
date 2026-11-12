import type { Page } from '@playwright/test'

import { addMedialuna, ensureCashOpen, expect, test } from './fixtures'

const METHOD = 'Transferencia'

async function setMethod(page: Page, on: boolean) {
  await page.goto('/config?tab=pagos')
  const sw = page.getByRole('switch', { name: `Habilitar ${METHOD}` })
  await expect(sw).toBeVisible()
  if ((await sw.getAttribute('aria-checked')) !== String(on)) {
    await sw.click()
    await expect(sw).toHaveAttribute('aria-checked', String(on))
  }
  return sw
}

/** Whether the POS checkout dialog offers METHOD. */
async function checkoutOffers(page: Page) {
  await page.goto('/pos')
  await ensureCashOpen(page)
  await addMedialuna(page)
  await page.getByRole('button', { name: /COBRAR/ }).click()
  const dialog = page.getByRole('dialog', { name: 'Cobrar' })
  await expect(dialog.getByRole('button', { name: 'Efectivo' })).toBeVisible()
  const offered = await dialog.getByRole('button', { name: METHOD, exact: true }).isVisible()
  await page.keyboard.press('Escape')
  await expect(dialog).toBeHidden()
  return offered
}

test('toggling a payment method hides it from the POS checkout', async ({ page }) => {
  try {
    const sw = await setMethod(page, false)
    await expect(page.getByRole('row').filter({ has: sw }).getByText('Oculto en el cobro')).toBeVisible()
    expect(await checkoutOffers(page)).toBe(false)

    const on = await setMethod(page, true)
    await expect(page.getByRole('row').filter({ has: on }).getByText('Oculto en el cobro')).toBeHidden()
    expect(await checkoutOffers(page)).toBe(true)
  } finally {
    await setMethod(page, true)
  }
})
