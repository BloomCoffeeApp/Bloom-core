import { expect, test } from './fixtures'
import {
  authHeaders,
  cartLine,
  confirmCheckout,
  createCustomerApi,
  money,
  openCheckout,
  openPos,
  pickCustomer,
  productTile,
  statCard,
  ticketNumber,
  uid,
} from './helpers'

test.describe('POS', () => {
  test('modifiers, quantities and removing a line', async ({ page, errors }) => {
    await openPos(page)

    await productTile(page, 'Latte').click()
    const mod = page.getByRole('dialog', { name: 'Latte' })
    await expect(mod.getByText('Tipo de leche')).toBeVisible()
    await mod.getByRole('button', { name: /^Bebida de avena/ }).click()
    await mod.getByRole('button', { name: /^Shot extra/ }).click()
    await mod.getByRole('button', { name: 'Sumar' }).click()
    // (3.400 + 600 + 800) × 2
    await mod.getByRole('button', { name: `Agregar · ${money(960_000)}` }).click()
    await expect(mod).toBeHidden()

    const latte = cartLine(page, 'Latte')
    await expect(latte).toContainText('Bebida de avena · Shot extra')
    await expect(latte).toContainText(money(960_000))

    await productTile(page, 'Medialuna').click()
    const medialuna = cartLine(page, 'Medialuna')
    await medialuna.getByRole('button', { name: 'Sumar' }).click()
    await expect(medialuna).toContainText(money(180_000))
    await expect(page.getByText('Subtotal · 4 ítems')).toBeVisible()

    await medialuna.getByRole('button', { name: 'Restar' }).click()
    await medialuna.getByRole('button', { name: 'Quitar' }).click()
    await expect(medialuna).toHaveCount(0)
    await expect(page.getByText('Subtotal · 2 ítems')).toBeVisible()

    await page.getByRole('button', { name: 'Vaciar' }).click()
    await expect(page.getByText('Carrito vacío')).toBeVisible()
    expect(errors.consoleErrors).toEqual([])
  })

  test('line and sale discounts (admin) and a cash sale with the exact amount', async ({ page }) => {
    await openPos(page)
    await productTile(page, 'Budín de limón').click()
    await productTile(page, 'Budín de limón').click()
    const line = cartLine(page, 'Budín de limón')
    await expect(line).toContainText(money(500_000))

    // 20% off the line → 4.000
    await line.getByRole('button', { name: /Budín de limón/ }).click()
    const lineDlg = page.getByRole('dialog', { name: 'Budín de limón' })
    await lineDlg.getByRole('button', { name: '20%' }).click()
    await lineDlg.getByRole('button', { name: 'Guardar' }).click()
    await expect(line).toContainText(money(400_000))

    // 10% off the sale → 3.600
    await page.getByRole('button', { name: 'Descuento' }).click()
    const disc = page.getByRole('dialog', { name: 'Descuento a la venta' })
    await disc.getByRole('button', { name: 'Porcentaje' }).click()
    await disc.getByRole('button', { name: '10%' }).click()
    await expect(disc).toContainText(money(40_000))
    await disc.getByRole('button', { name: 'Aplicar' }).click()
    await expect(page.getByText('Descuento 10%')).toBeVisible()

    const dialog = await openCheckout(page)
    await expect(dialog.getByText(money(360_000)).first()).toBeVisible()
    await dialog.getByRole('button', { name: 'Exacto' }).click()
    const done = await confirmCheckout(page, dialog)
    await expect(done).toContainText(money(360_000))
  })

  test('split payment: cash with change + debit', async ({ page }) => {
    await openPos(page)
    await productTile(page, 'Tostado de jamón y queso').click()
    const dialog = await openCheckout(page)

    await dialog.getByRole('button', { name: 'Dividir pago' }).click()
    await expect(dialog.getByRole('button', { name: 'Pago dividido activado' })).toBeVisible()
    await dialog.getByLabel('Monto Efectivo').fill('2000')
    await expect(dialog.getByText('Falta asignar')).toBeVisible()
    const confirm = dialog.getByRole('button', { name: /Confirmar cobro/ })
    await expect(confirm).toBeDisabled()

    await dialog.getByRole('button', { name: 'Débito' }).click()
    await expect(dialog.getByLabel('Monto Débito')).toHaveValue('3.200')
    await expect(dialog.getByText('Falta asignar')).toBeHidden()

    await dialog.getByLabel('Efectivo recibido').fill('5000')
    await expect(dialog.getByText(money(300_000))).toBeVisible() // change

    const done = await confirmCheckout(page, dialog)
    await expect(done.getByText('Vuelto')).toBeVisible()
    await expect(done).toContainText(money(300_000))
    const n = await ticketNumber(done)

    // The sale keeps both payments
    await page.goto('/ventas')
    await page.getByPlaceholder('N° de ticket').fill(String(n))
    await page.getByRole('row').filter({ hasText: `#${n}` }).click()
    const sheet = page.getByRole('dialog', { name: new RegExp(`Ticket #${n}`) })
    await expect(sheet.getByText(`Entregó ${money(500_000)} · vuelto ${money(300_000)}`)).toBeVisible()
    await expect(sheet.getByText('Débito')).toBeVisible()
  })

  test('a sale with a customer adds loyalty points', async ({ page, request }) => {
    const c = await createCustomerApi(page, request, { name: `Puntos ${uid()}` })
    await openPos(page)
    await productTile(page, 'Latte').click()
    await page.getByRole('dialog', { name: 'Latte' }).getByRole('button', { name: `Agregar · ${money(340_000)}` }).click()
    await pickCustomer(page, c.name)
    await expect(page.getByText('Suma 3 puntos')).toBeVisible() // $1.000 per point

    const dialog = await openCheckout(page)
    const done = await confirmCheckout(page, dialog)
    await expect(done.getByText(`${c.name} sumó 3 puntos (total 3).`)).toBeVisible()
  })

  test('cuenta corriente needs a customer and books the debt', async ({ page, request }) => {
    const c = await createCustomerApi(page, request, { name: `Cuenta ${uid()}` })
    await openPos(page)
    await productTile(page, 'Medialuna').click()

    let dialog = await openCheckout(page)
    await expect(dialog.getByRole('button', { name: 'Cuenta corriente' })).toBeDisabled()
    await page.keyboard.press('Escape')
    await expect(dialog).toBeHidden()

    await pickCustomer(page, c.name)
    dialog = await openCheckout(page)
    await dialog.getByRole('button', { name: 'Cuenta corriente' }).click()
    await confirmCheckout(page, dialog)

    await page.goto(`/clientes/${c.id}`)
    const account = page.locator('[data-slot="card"]').filter({ hasText: 'Saldo adeudado' })
    await expect(account).toContainText(money(90_000))
    await expect(account.getByText('Consumo a cuenta')).toBeVisible()
  })

  test('redeeming loyalty points discounts the sale', async ({ page, request }) => {
    const c = await createCustomerApi(page, request, { name: `Canje ${uid()}` })
    const res = await request.post(`/api/customers/${c.id}/points`, {
      data: { points: 100, reason: 'Carga e2e' },
      headers: await authHeaders(page),
    })
    expect(res.ok(), await res.text()).toBeTruthy()

    await openPos(page)
    await productTile(page, 'Tostado de jamón y queso').click()
    await pickCustomer(page, c.name)
    await expect(page.getByText(/Puede canjear 100 pts por/)).toBeVisible()
    await page.getByRole('button', { name: 'Canjear' }).click()
    await expect(page.getByText('Canje de puntos')).toBeVisible()

    const dialog = await openCheckout(page)
    await expect(dialog.getByText(money(20_000)).first()).toBeVisible() // 5.200 − 5.000
    await confirmCheckout(page, dialog)

    await page.goto(`/clientes/${c.id}`)
    const points = page.locator('[data-slot="card"]').filter({ has: page.getByText('Puntos', { exact: true }) }).last()
    await expect(points).toContainText('-100')
  })

  test('keyboard: F2 search + Enter adds, F9 checkout, Enter confirms; ticket prints', async ({ page }) => {
    await openPos(page)
    await page.keyboard.press('F2')
    const search = page.getByRole('textbox', { name: 'Buscar producto' })
    await expect(search).toBeFocused()
    await search.fill('medialu')
    await page.keyboard.press('Enter')
    await expect(cartLine(page, 'Medialuna')).toBeVisible()
    await expect(search).toHaveValue('')

    await page.keyboard.press('F9')
    const dialog = page.getByRole('dialog', { name: 'Cobrar' })
    await expect(dialog.getByText('Total a cobrar')).toBeVisible()
    await page.keyboard.press('Enter')
    const done = page.getByRole('dialog').filter({ hasText: '¡Venta cobrada!' })
    await expect(done).toBeVisible()
    const n = await ticketNumber(done)

    const ticket = page.waitForResponse((r) => /\/api\/sales\/\d+\/ticket$/.test(r.url()) && r.ok())
    await done.getByRole('button', { name: 'Imprimir ticket' }).click()
    const body = await (await ticket).json()
    expect(body.sale.number).toBe(n)

    await done.getByRole('button', { name: 'Nueva venta' }).click()
    await expect(done).toBeHidden()
    await expect(page.getByText('Carrito vacío')).toBeVisible()
  })

  test('courtesy ("invita la casa"): $0 charged, badge in sales, separate line in the cash close / Z', async ({ page, request, errors }) => {
    await openPos(page)
    const headers = await authHeaders(page)
    const before = await (await request.get('/api/cash/current', { headers })).json()

    await productTile(page, 'Medialuna').click()
    await cartLine(page, 'Medialuna').getByRole('button', { name: 'Sumar' }).click()
    await openCheckout(page)
    await page.getByRole('switch', { name: 'Cortesía (no se cobra)' }).click()
    const dialog = page.getByRole('dialog', { name: 'Cortesía' })
    const total = dialog.getByTestId('courtesy-total')
    await expect(total).toContainText(money(0))
    await expect(total.locator('.line-through')).toHaveText(money(180_000))
    await expect(dialog.getByRole('button', { name: 'Efectivo' })).toHaveCount(0) // no payment inputs
    const reason = `Proveedor ${uid()}`
    await dialog.getByLabel(/Para quién \/ motivo/).fill(reason)
    await dialog.getByRole('button', { name: 'Registrar cortesía' }).click()
    const done = page.getByRole('dialog').filter({ hasText: '¡Cortesía registrada!' })
    await expect(done).toBeVisible()
    await expect(done).toContainText(money(180_000))
    const n = await ticketNumber(done)
    await done.getByRole('button', { name: 'Nueva venta' }).click()

    // Sales list: badge + $0, detail keeps the reason and the menu value.
    await page.goto('/ventas')
    await page.getByPlaceholder('N° de ticket').fill(String(n))
    const row = page.getByRole('row').filter({ hasText: `#${n}` })
    await expect(row.getByTestId('courtesy-badge')).toBeVisible()
    await row.click()
    const sheet = page.getByRole('dialog', { name: new RegExp(`Ticket #${n}`) })
    await expect(sheet.getByTestId('courtesy-note')).toContainText(reason)
    await expect(sheet.getByTestId('courtesy-note')).toContainText(money(180_000))
    await page.keyboard.press('Escape')

    // Cash: nothing expected changed; the courtesy shows apart.
    const cur = await (await request.get('/api/cash/current', { headers })).json()
    expect(cur.expected_cash_cents).toBe(before.expected_cash_cents)
    expect(cur.sales_total_cents).toBe(before.sales_total_cents)
    expect(cur.tickets).toBe(before.tickets)
    expect(cur.courtesy_count).toBe(before.courtesy_count + 1)
    expect(cur.courtesy_cost_cents).toBeGreaterThan(0)
    const line = `Cortesías: ${cur.courtesy_count} (${money(cur.courtesy_cents)} a precio de carta, costo ${money(cur.courtesy_cost_cents)})`
    await page.goto('/caja')
    await expect(statCard(page, 'Ventas del turno')).toContainText(line)

    await page.getByRole('button', { name: 'Cerrar caja' }).click()
    const close = page.getByRole('dialog', { name: /Cerrar caja · arqueo/ })
    await expect(close.getByTestId('close-courtesy')).toContainText(line)
    await close.getByLabel('Contado Efectivo').fill(String(Math.round(cur.expected_cash_cents / 100)))
    await close.getByRole('button', { name: 'Cerrar caja' }).click()
    await expect(close).toBeHidden()
    const z = page.getByRole('dialog', { name: /Cierre de caja #\d+/ })
    const zLine = z.getByText(`Cortesías (${cur.courtesy_count})`).locator('..')
    await expect(zLine).toContainText(`${money(cur.courtesy_cents)} a precio de carta`)
    // What they cost is shown as a loss.
    await expect(z.getByText('Pérdida por cortesías (costo)').locator('..')).toContainText(`−${money(cur.courtesy_cost_cents)}`)
    await expect(z.getByText('Ventas', { exact: true }).locator('..')).toContainText(money(cur.sales_total_cents))
    expect(errors.consoleErrors).toEqual([])
  })
})
