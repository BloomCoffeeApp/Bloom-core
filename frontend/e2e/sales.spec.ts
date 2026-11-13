import type { Page } from '@playwright/test'

import { addMedialuna, expect, test } from './fixtures'
import { authHeaders, confirmCheckout, ensureCashOpenApi, openCheckout, openPos, ticketNumber } from './helpers'

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

  test('delivery sale: the detail shows the shipping line and the total includes it', async ({ page, request }) => {
    await ensureCashOpenApi(page, request)
    const headers = await authHeaders(page)
    const products: { id: number; name: string; price_cents: number }[] = await (await request.get('/api/products', { headers })).json()
    const med = products.find((x) => x.name === 'Medialuna')!
    const fee = 50000
    const res = await request.post('/api/sales', {
      headers,
      data: { items: [{ product_id: med.id }], channel: 'delivery', delivery_fee_cents: fee, payments: [{ method: 'efectivo', amount_cents: med.price_cents + fee }] },
    })
    expect(res.ok(), await res.text()).toBeTruthy()
    const n = (await res.json()).number as number
    await page.goto('/ventas')
    await page.getByPlaceholder('N° de ticket').fill(String(n))
    await page.getByRole('row').filter({ hasText: `#${n}` }).click()
    const sheet = page.getByRole('dialog', { name: new RegExp(`Ticket #${n}`) })
    await expect(sheet.getByText('Envío', { exact: true })).toBeVisible()
    await expect(sheet.getByText(/500,00/).first()).toBeVisible()
  })

  test('optional tip: offered at checkout, on top of the total, recorded on the sale', async ({ page, request }) => {
    const headers = await authHeaders(page)
    expect((await request.put('/api/settings/tips', { headers, data: { enabled: true, percents: [10, 15] } })).ok()).toBeTruthy()
    try {
      await openPos(page)
      await addMedialuna(page)
      const dialog = await openCheckout(page)
      const picker = dialog.getByTestId('tip-picker')
      await expect(picker).toContainText('Propina (opcional)')
      await picker.getByRole('button', { name: /^10 %/ }).click()
      await expect(dialog.getByTestId('tip-picker')).toContainText('La propina va aparte del total de la venta')
      const done = await confirmCheckout(page, dialog)
      const n = await ticketNumber(done)
      await page.goto('/ventas')
      await page.getByPlaceholder('N° de ticket').fill(String(n))
      await page.getByRole('row').filter({ hasText: `#${n}` }).click()
      const sheet = page.getByRole('dialog', { name: new RegExp(`Ticket #${n}`) })
      await expect(sheet.getByTestId('sale-tip')).toContainText('$')
    } finally {
      await request.put('/api/settings/tips', { headers, data: { enabled: false, percents: [10, 15, 20] } })
    }
  })
})
