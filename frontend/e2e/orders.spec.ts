import { expect, test } from './fixtures'
import { authHeaders, confirmCheckout, money, openCheckout, openPos, productTile, ticketNumber } from './helpers'

test.describe('Order screen', () => {
  test('a POS sale appears on the order screen and moves through its states', async ({ page, errors }) => {
    await openPos(page)
    await productTile(page, 'Latte').click()
    await page.getByRole('dialog', { name: 'Latte' }).getByRole('button', { name: `Agregar · ${money(340_000)}` }).click()
    await page.getByRole('textbox', { name: 'Mesa' }).fill('12')
    const done = await confirmCheckout(page, await openCheckout(page))
    const n = await ticketNumber(done)

    await page.goto('/pedidos')
    await expect(page.getByRole('heading', { level: 1, name: /^Pedidos/ })).toBeVisible()
    const card = page.getByTestId('order-card').filter({ hasText: `Ticket #${n}` })
    await expect(card).toHaveAttribute('data-status', 'received')
    await expect(card).toContainText('Latte')
    await expect(card).toContainText('12')
    await expect(card).toHaveAttribute('data-level', 'ok')
    await expect(card.getByTestId('order-timer')).toContainText(/^\s*\d+:\d\d/)
    // Browsers need a click before playing sound: offered once.
    await expect(page.getByRole('button', { name: 'Activar sonido' })).toBeVisible()
    await page.getByRole('button', { name: 'Activar sonido' }).click()
    await expect(page.getByRole('button', { name: 'Activar sonido' })).toBeHidden()

    await card.getByRole('button', { name: 'Empezar' }).click()
    await expect(card).toHaveAttribute('data-status', 'preparing')
    await expect(page.getByRole('region', { name: 'En preparación' }).getByTestId('order-card').filter({ hasText: `Ticket #${n}` })).toBeVisible()
    await card.getByRole('button', { name: 'Listo' }).click()
    await expect(card).toHaveAttribute('data-status', 'ready')
    await card.getByRole('button', { name: 'Entregado' }).click()
    await expect(card).toHaveCount(0)

    // Dashboard line ("hoy: N atrasados, promedio X min").
    await page.goto('/')
    await expect(page.getByTestId('orders-strip')).toContainText(/atrasado/)
    await expect(page.getByTestId('orders-strip')).toContainText(/promedio/)
    expect(errors.consoleErrors).toEqual([])
  })

  test('bakery stays at the counter and the targets are configurable', async ({ page, request }) => {
    const headers = await authHeaders(page)
    await page.goto('/config?tab=pedidos')
    const target = page.getByLabel('Tiempo objetivo').first()
    await expect(target).toBeVisible()
    await target.fill('9')
    await page.getByRole('button', { name: 'Guardar' }).first().click()
    await expect(page.getByText('Pantalla de pedidos guardada')).toBeVisible()
    const s = await (await request.get('/api/orders/settings', { headers })).json()
    expect(s.targets.salon).toBe(9)
    s.targets.salon = 8
    await request.put('/api/orders/settings', { headers, data: s })

    // A bakery-only sale doesn't reach the screen.
    await openPos(page)
    await productTile(page, 'Medialuna').click()
    const n = await ticketNumber(await confirmCheckout(page, await openCheckout(page)))
    await page.goto('/pedidos')
    await expect(page.getByRole('heading', { level: 1, name: /^Pedidos/ })).toBeVisible()
    await page.waitForTimeout(2500) // one polling round
    await expect(page.getByTestId('order-card').filter({ hasText: `Ticket #${n}` })).toHaveCount(0)
  })
})
