import type { APIRequestContext, Page } from '@playwright/test'

import { expect, test } from './fixtures'
import { authHeaders, confirmCheckout, openCheckout, openPos, productTile, ticketNumber } from './helpers'

/** «Insumos según el canal»: configured in the product editor, consumed by a counter «Para llevar» sale,
 * not by «Salón», and given back when the sale is voided. */
const PRODUCT = 'Budín de limón'
const CUP = 'Vaso térmico 8oz'

async function stockOf(page: Page, request: APIRequestContext, name: string) {
  const items: { name: string; current_qty: number }[] = await (await request.get('/api/stock/items', { headers: await authHeaders(page) })).json()
  return items.find((i) => i.name === name)!.current_qty
}

async function sell(page: Page, channel: 'Salón' | 'Para llevar') {
  await openPos(page)
  await page.getByRole('button', { name: channel, exact: true }).click()
  await expect(page.getByRole('button', { name: channel, exact: true })).toHaveAttribute('aria-pressed', 'true')
  await page.getByRole('textbox', { name: 'Buscar producto' }).fill(PRODUCT)
  await productTile(page, PRODUCT).click()
  const done = await confirmCheckout(page, await openCheckout(page))
  const n = await ticketNumber(done)
  await page.keyboard.press('Escape')
  return n
}

test('take-away supplies are configured per product and consumed only by «Para llevar»; a void restores them', async ({ page, request }) => {
  test.setTimeout(90_000)
  await page.goto('/productos')
  await page.getByPlaceholder('Buscar producto…').fill(PRODUCT)
  await page.getByRole('row').filter({ hasText: PRODUCT }).click()
  const editor = page.getByRole('dialog', { name: PRODUCT })
  const box = editor.getByTestId('channel-supplies')
  await box.scrollIntoViewIfNeeded()
  await box.getByRole('tab', { name: /Para llevar/ }).click()
  await box.getByRole('button', { name: 'Agregar insumo' }).click()
  await box.getByLabel('Insumo', { exact: true }).selectOption({ label: `${CUP} (u)` })
  await box.getByRole('button', { name: 'Guardar insumos' }).click()
  await expect(page.getByText('Insumos según el canal guardados')).toBeVisible()
  await page.keyboard.press('Escape')

  const start = await stockOf(page, request, CUP)
  await sell(page, 'Salón')
  expect(await stockOf(page, request, CUP)).toBe(start)
  const ticket = await sell(page, 'Para llevar')
  expect(await stockOf(page, request, CUP)).toBe(start - 1)

  const headers = await authHeaders(page)
  const sales: { items: { id: number; number: number }[] } | { id: number; number: number }[] = await (await request.get('/api/sales', { headers })).json()
  const list = Array.isArray(sales) ? sales : sales.items
  const sale = list.find((s) => s.number === ticket)!
  const v = await request.post(`/api/sales/${sale.id}/void`, { headers, data: { reason: 'Prueba de envases' } })
  expect(v.ok(), await v.text()).toBeTruthy()
  expect(await stockOf(page, request, CUP)).toBe(start)

  // Clean up so other specs see the product as before.
  const products: { id: number; name: string }[] = await (await request.get('/api/products', { headers })).json()
  const pid = products.find((p) => p.name === PRODUCT)!.id
  await request.put(`/api/products/${pid}/channel-supplies`, { headers, data: { rows: [] } })
})
