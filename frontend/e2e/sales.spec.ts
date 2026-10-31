import type { Page } from '@playwright/test'

import { addMedialuna, expect, test } from './fixtures'
import { confirmCheckout, openCheckout, openPos, ticketNumber } from './helpers'

/** Sells one medialuna in cash and returns the ticket number. */
async function sellOne(page: Page) {
  await openPos(page)
  await addMedialuna(page)
  const done = await confirmCheckout(page, await openCheckout(page))
  return ticketNumber(done)
}

async function pickOption(page: Page, current: string, option: string) {
  await page.getByRole('combobox').filter({ hasText: current }).click()
  await page.getByRole('option', { name: option, exact: true }).click()
}

test.describe('Ventas', () => {
  test('list, filters and presets', async ({ page, errors }) => {
    const n = await sellOne(page)
    await page.goto('/ventas')
    const row = page.getByRole('row').filter({ hasText: `#${n}` })
    await expect(row).toBeVisible() // "Hoy" by default
    await expect(row).toContainText('Efectivo')

    await pickOption(page, 'Todos los medios', 'Débito')
    await expect(row).toBeHidden()
    await pickOption(page, 'Débito', 'Efectivo')
    await expect(row).toBeVisible()

    await pickOption(page, 'Todos los estados', 'Anuladas')
    await expect(row).toBeHidden()
    await pickOption(page, 'Anuladas', 'Completadas')
    await expect(row).toBeVisible()

    // Presets: the demo history has sales in the last 30 days
    for (const preset of ['Ayer', '7 días', '30 días']) {
      await page.getByRole('button', { name: preset, exact: true }).click()
      await expect(page.getByText(/No hay ventas|N°/).first()).toBeVisible()
    }
    await page.getByRole('button', { name: 'Rango', exact: true }).click()
    await expect(page.locator('input[type="date"]')).toHaveCount(2)

    // Ticket number search ignores the dates
    await page.getByPlaceholder('N° de ticket').fill(String(n))
    await expect(page.getByRole('row')).toHaveCount(2) // header + the ticket
    await expect(row).toBeVisible()
    expect(errors.consoleErrors).toEqual([])
  })

  test('detail, reprint and void with a reason', async ({ page }) => {
    const n = await sellOne(page)
    await page.goto('/ventas')
    await page.getByPlaceholder('N° de ticket').fill(String(n))
    const row = page.getByRole('row').filter({ hasText: `#${n}` })
    await row.click()

    const sheet = page.getByRole('dialog', { name: new RegExp(`Ticket #${n}`) })
    await expect(sheet.getByText('Medialuna')).toBeVisible()
    await expect(sheet.getByText('Pagos')).toBeVisible()

    const ticket = page.waitForResponse((r) => r.url().endsWith(`/ticket`) && r.ok())
    await sheet.getByRole('button', { name: 'Reimprimir' }).click()
    expect((await (await ticket).json()).sale.number).toBe(n)

    await sheet.getByRole('button', { name: 'Anular' }).click()
    const confirm = page.getByRole('alertdialog', { name: `¿Anular el ticket #${n}?` })
    await confirm.getByLabel('Motivo').fill('Error de carga e2e')
    await confirm.getByRole('button', { name: 'Anular venta' }).click()
    await expect(confirm).toBeHidden()

    await expect(sheet.getByText('Anulado', { exact: true })).toBeVisible()
    await expect(sheet.getByText(/Motivo: Error de carga e2e/)).toBeVisible()
    await expect(sheet.getByRole('button', { name: 'Anular' })).toBeHidden()
    await page.keyboard.press('Escape')

    await expect(row.getByText('Anulada')).toBeVisible()
    await page.getByPlaceholder('N° de ticket').clear()
    await pickOption(page, 'Todos los estados', 'Anuladas')
    await expect(row).toBeVisible()
  })
})
