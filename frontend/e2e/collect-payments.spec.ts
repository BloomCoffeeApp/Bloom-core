import fs from 'node:fs'

import type { APIRequestContext, Page } from '@playwright/test'

import { expect, test } from './fixtures'
import { authHeaders, money, openCheckout, openPos, productTile, ticketNumber } from './helpers'

/**
 * Cobros (Pro `payments`) with the simulated provider (FakeProvider, only outside the .exe):
 * QR shown on a registered customer screen, transfer confirmed by the cashier, refund from the sale.
 */
const SHOTS = process.env.BLOOM_SHOTS_DIR
const LATTE = 340_000

async function shot(page: Page, name: string) {
  if (!SHOTS) return
  fs.mkdirSync(SHOTS, { recursive: true })
  await page.screenshot({ path: `${SHOTS}/${name}.png` })
}

async function setup(page: Page, request: APIRequestContext, body: Record<string, unknown>) {
  const headers = await authHeaders(page)
  const res = await request.put('/api/collect/config', { data: body, headers })
  expect(res.ok(), await res.text()).toBeTruthy()
  const screens = await request.get('/api/collect/screens', { headers })
  let screen = ((await screens.json()) as { id: number; name: string; path: string }[]).find((s) => s.name === 'Tablet mostrador')
  if (!screen) {
    const r = await request.post('/api/collect/screens', { data: { name: 'Tablet mostrador' }, headers })
    screen = await r.json()
  }
  return screen!
}

async function checkoutWith(page: Page, method: string) {
  await openPos(page)
  await productTile(page, 'Latte').click()
  const mod = page.getByRole('dialog', { name: 'Latte' })
  if (await mod.isVisible().catch(() => false)) await mod.getByRole('button', { name: /^Agregar/ }).click()
  const checkout = await openCheckout(page)
  await checkout.getByRole('button', { name: method, exact: true }).click()
  await checkout.getByRole('button', { name: /Confirmar cobro/ }).click()
  await expect(checkout).toBeHidden()
}

test.describe('Cobros con QR y transferencia', () => {
  test('QR charge shows on the customer screen and completes the sale', async ({ page, request, context, errors }) => {
    const screen = await setup(page, request, { provider: 'fake' })
    const tv = await context.newPage()
    await tv.setViewportSize({ width: 1280, height: 800 })
    await tv.goto(screen.path)
    await expect(tv.getByTestId('screen-idle')).toBeVisible()

    await checkoutWith(page, 'QR Mercado Pago')
    const dlg = page.getByRole('dialog', { name: 'Cobro con QR' })
    await dlg.getByRole('button', { name: 'Tablet mostrador' }).click()
    await dlg.getByRole('button', { name: 'Generar QR' }).click()
    await expect(dlg.getByTestId('pos-charge-qr')).toBeVisible()
    await expect(dlg.getByText('Esperando que el cliente pague')).toBeVisible()
    await shot(page, 'pos-charge-dialog')

    await expect(tv.getByTestId('screen-qr')).toBeVisible()
    await expect(tv.getByTestId('screen-total')).toHaveText(money(LATTE))
    await expect(tv.getByText('Latte')).toBeVisible()
    await shot(tv, 'customer-screen-qr')

    await dlg.getByRole('button', { name: 'Simular pago (prueba)' }).click()
    const done = page.getByRole('dialog').filter({ hasText: '¡Venta cobrada!' })
    await expect(done).toBeVisible()
    await expect(tv.getByTestId('screen-approved')).toBeVisible()
    await shot(tv, 'customer-screen-approved')
    const n = await ticketNumber(done)
    await done.getByRole('button', { name: 'Nueva venta' }).click()

    // Refund (partial) from the sale detail.
    await page.goto('/ventas')
    await page.getByPlaceholder('N° de ticket').fill(String(n))
    await page.getByRole('row').filter({ hasText: `#${n}` }).click()
    const sheet = page.getByRole('dialog', { name: new RegExp(`Ticket #${n}`) })
    const panel = sheet.getByTestId('sale-refund-panel')
    await expect(panel).toBeVisible()
    await panel.getByRole('button', { name: 'Devolver' }).click()
    const refund = page.getByRole('dialog', { name: 'Devolver por Mercado Pago' })
    await refund.getByLabel('Monto a devolver').fill('1000')
    await refund.getByRole('button', { name: /^Devolver \$/ }).click()
    await expect(refund).toBeHidden()
    await expect(panel.getByText(`Devuelto ${money(100_000)}`)).toBeVisible()
    await shot(page, 'sale-refund')
    expect(errors.consoleErrors).toEqual([])
    await tv.close()
  })

  test('transfer: alias on the customer screen and «Pago recibido»', async ({ page, request, context }) => {
    const screen = await setup(page, request, {
      transfer: { enabled: true, alias: 'cafe.ejemplo.mp', cbu: '', holder: 'Café Ejemplo SRL', bank: 'Banco Ficticio', cuit: '' },
    })
    const tv = await context.newPage()
    await tv.goto(screen.path)
    await checkoutWith(page, 'Transferencia')
    const dlg = page.getByRole('dialog', { name: 'Cobro por transferencia' })
    await dlg.getByRole('button', { name: 'Tablet mostrador' }).click()
    await dlg.getByRole('button', { name: 'Mostrar datos' }).click()
    await expect(dlg.getByTestId('transfer-box')).toContainText('cafe.ejemplo.mp')
    await expect(tv.getByTestId('screen-alias')).toHaveText('cafe.ejemplo.mp')
    await shot(tv, 'customer-screen-transfer')
    await dlg.getByRole('button', { name: 'Pago recibido' }).click()
    await expect(page.getByRole('dialog').filter({ hasText: '¡Venta cobrada!' })).toBeVisible()
    await expect(tv.getByTestId('screen-approved')).toBeVisible()
    await tv.close()
  })

  test('settings page explains interoperability and registers screens', async ({ page }) => {
    await page.goto('/config?tab=cobros')
    await expect(page.getByTestId('collect-interop-note')).toContainText('interoperable')
    await expect(page.getByText('Pantallas del cliente')).toBeVisible()
    await shot(page, 'settings-cobros')
  })
})
