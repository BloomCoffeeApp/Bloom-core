import { expect, test } from './fixtures'
import { authHeaders, createCustomerApi, ensureCashOpenApi, money, uid } from './helpers'

test.describe('Clientes', () => {
  test('create, edit, adjust points, search and deactivate', async ({ page, errors }) => {
    const name = `Cliente ${uid()}`
    await page.goto('/clientes')
    await page.getByRole('button', { name: 'Nuevo cliente' }).click()
    const form = page.getByRole('dialog', { name: 'Nuevo cliente' })
    await form.getByLabel('Nombre').fill(name)
    await form.getByLabel('Teléfono').fill('11 5555-9999')
    await form.getByLabel('Email').fill('cliente.e2e@example.com')
    await form.getByLabel('Cumpleaños').fill('1990-05-20')
    await form.getByLabel('Límite cuenta corriente').fill('20000')
    await form.getByLabel('Preferencias / notas').fill('Flat white con avena')
    await form.getByRole('button', { name: 'Guardar' }).click()

    await expect(page).toHaveURL(/\/clientes\/\d+$/)
    await expect(page.getByRole('heading', { level: 1, name })).toBeVisible()
    await expect(page.getByText('11 5555-9999')).toBeVisible()
    await expect(page.getByText('Flat white con avena')).toBeVisible()
    await expect(page.getByText(`Límite ${money(2_000_000)}`)).toBeVisible()
    await expect(page.getByText('Sin compras todavía')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Registrar pago' })).toBeDisabled()

    // Edit
    await page.getByRole('button', { name: 'Editar' }).click()
    const edit = page.getByRole('dialog', { name: 'Editar cliente' })
    await edit.getByLabel('Teléfono').fill('11 5555-8888')
    await edit.getByRole('button', { name: 'Guardar' }).click()
    await expect(edit).toBeHidden()
    await expect(page.getByText('11 5555-8888')).toBeVisible()

    // Points
    await page.getByRole('button', { name: 'Ajustar' }).click()
    const pts = page.getByRole('dialog', { name: 'Ajustar puntos' })
    await pts.getByLabel('Puntos').fill('20')
    await expect(pts.getByText('Quedaría en 20 pts')).toBeVisible()
    await pts.getByLabel('Motivo').fill('Bienvenida e2e')
    await pts.getByRole('button', { name: 'Guardar ajuste' }).click()
    await expect(pts).toBeHidden()
    await expect(page.getByText('Bienvenida e2e')).toBeVisible()

    // Search in the list
    await page.getByRole('link', { name: 'Clientes' }).first().click()
    await page.getByPlaceholder('Buscar por nombre, teléfono o email…').fill('5555-8888')
    const row = page.getByRole('row').filter({ hasText: name })
    await expect(row).toBeVisible()
    await expect(row).toContainText('20')

    // Deactivate
    await row.click()
    await page.getByRole('button', { name: 'Desactivar' }).click()
    await page.getByRole('alertdialog', { name: `¿Desactivar a ${name}?` }).getByRole('button', { name: 'Desactivar' }).click()
    await expect(page).toHaveURL(/\/clientes$/)
    await page.getByPlaceholder('Buscar por nombre, teléfono o email…').fill(name)
    await expect(page.getByText('No encontramos clientes')).toBeVisible()
    expect(errors.consoleErrors).toEqual([])
  })

  test('purchase history and cuenta corriente payments', async ({ page, request }) => {
    const headers = await authHeaders(page)
    const c = await createCustomerApi(page, request, { name: `Deudor ${uid()}` })
    await ensureCashOpenApi(page, request)
    const products = await (await request.get('/api/products', { headers })).json()
    const medialuna = products.find((p: { name: string }) => p.name === 'Medialuna')
    const sale = await request.post('/api/sales', {
      headers,
      data: {
        items: [{ product_id: medialuna.id, qty: 2 }],
        customer_id: c.id,
        payments: [{ method: 'cuenta_corriente', amount_cents: 2 * medialuna.price_cents }],
      },
    })
    expect(sale.ok(), await sale.text()).toBeTruthy()
    const { number } = await sale.json()
    const debt = 2 * medialuna.price_cents

    await page.goto(`/clientes/${c.id}`)
    const history = page.locator('[data-slot="card"]').filter({ hasText: 'Historial de compras' })
    await expect(history.getByText(`#${number}`, { exact: false })).toBeVisible()
    await expect(history.getByText('1 tickets', { exact: true })).toBeVisible()
    const account = page.locator('[data-slot="card"]').filter({ hasText: 'Saldo adeudado' })
    await expect(account).toContainText(money(debt))

    // In the "Con deuda" segment
    await page.goto('/clientes?segmento=deudores')
    await expect(page.getByRole('row').filter({ hasText: c.name })).toContainText(money(debt))

    // Pay half, then the rest
    await page.goto(`/clientes/${c.id}`)
    await account.getByRole('button', { name: 'Registrar pago' }).click()
    let pay = page.getByRole('dialog', { name: 'Registrar pago' })
    await pay.getByRole('button', { name: 'Mitad' }).click()
    await pay.getByRole('button', { name: 'Registrar pago' }).click()
    await expect(pay).toBeHidden()
    await expect(account).toContainText(money(debt / 2))
    await expect(account.getByText('Pago · Efectivo')).toBeVisible()

    await account.getByRole('button', { name: 'Registrar pago' }).click()
    pay = page.getByRole('dialog', { name: 'Registrar pago' })
    await pay.getByLabel('Monto').fill(String(debt / 100 + 1)) // more than owed
    await expect(pay.getByText('No puede superar la deuda.')).toBeVisible()
    await pay.getByRole('button', { name: 'Total' }).click()
    await pay.getByRole('button', { name: 'Registrar pago' }).click()
    await expect(pay).toBeHidden()
    await expect(account).toContainText(money(0))
    await expect(account.getByRole('button', { name: 'Registrar pago' })).toBeDisabled()
  })
})
