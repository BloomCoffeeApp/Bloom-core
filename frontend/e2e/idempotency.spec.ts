import { addMedialuna, ensureCashOpen, expect, test } from './fixtures'
import { authHeaders } from './helpers'

/**
 * A sale whose answer is lost on the way (flaky Wi-Fi, a tablet that went to sleep) reaches the server but the
 * cashier sees an error and presses "Confirmar cobro" again. Before the idempotency key that registered the sale twice.
 */
test('a retry after a lost response registers the sale once', async ({ page, request }) => {
  await page.goto('/pos')
  await ensureCashOpen(page)
  const headers = await authHeaders(page)
  const total = async () => (await (await request.get('/api/sales?page_size=1', { headers })).json()).total as number
  const before = await total()

  const keys: string[] = []
  let lostOnce = false
  await page.route('**/api/sales', async (route) => {
    if (route.request().method() !== 'POST') return route.continue()
    keys.push(route.request().headers()['idempotency-key'] ?? '')
    if (!lostOnce) {
      lostOnce = true
      await route.fetch() // the server really processes it...
      return route.abort('connectionreset') // ...but the answer never arrives
    }
    return route.continue()
  })

  await addMedialuna(page)
  await page.getByRole('button', { name: /COBRAR/ }).click()
  const dialog = page.getByRole('dialog', { name: 'Cobrar' })
  await dialog.getByRole('button', { name: /Confirmar cobro/ }).click()
  await expect(page.getByText(/No se pudo conectar/)).toBeVisible()

  await dialog.getByRole('button', { name: /Confirmar cobro/ }).click() // the cashier retries
  await expect(page.getByRole('dialog').getByText('¡Venta cobrada!')).toBeVisible()

  expect(keys).toHaveLength(2)
  expect(keys[0]).toMatch(/^[0-9a-f]{32}$/)
  expect(keys[1], 'the retry of the same sale must reuse its key').toBe(keys[0])
  expect(await total(), 'one sale, not two').toBe(before + 1)
})

test('the next sale with the same content is a new sale (a new key)', async ({ page, request }) => {
  await page.goto('/pos')
  await ensureCashOpen(page)
  const headers = await authHeaders(page)
  const total = async () => (await (await request.get('/api/sales?page_size=1', { headers })).json()).total as number
  const before = await total()

  const keys: string[] = []
  page.on('request', (r) => {
    if (r.method() === 'POST' && r.url().endsWith('/api/sales')) keys.push(r.headers()['idempotency-key'] ?? '')
  })
  for (let i = 0; i < 2; i++) {
    await addMedialuna(page)
    await page.getByRole('button', { name: /COBRAR/ }).click()
    await page.getByRole('dialog', { name: 'Cobrar' }).getByRole('button', { name: /Confirmar cobro/ }).click()
    await expect(page.getByRole('dialog').getByText('¡Venta cobrada!')).toBeVisible()
    await page.keyboard.press('Escape')
  }
  expect(new Set(keys).size).toBe(2)
  expect(await total()).toBe(before + 2)
})
