import { expect, test } from './fixtures'
import { authHeaders, openPos, uid } from './helpers'

test('packages: define "Sachet 1 L", see stock as packages + loose, discard by package and all', async ({ page, request }) => {
  const headers = await authHeaders(page)
  const name = `Leche ${uid()}`
  const created = await request.post('/api/stock/items', {
    headers,
    data: { name, unit: 'ml', avg_cost_cents: 0.2, initial_qty: 4730 },
  })
  expect(created.ok(), await created.text()).toBeTruthy()

  await page.goto('/stock')
  await page.getByPlaceholder('Buscar insumo…').fill(name)
  const row = page.getByRole('row').filter({ hasText: name })
  await row.getByRole('button', { name: 'Acciones' }).click()
  await page.getByRole('menuitem', { name: 'Envases' }).click()
  const pk = page.getByRole('dialog', { name: `Envases de ${name}` })
  await pk.getByLabel('Nombre del envase 1').fill('Sachet 1 L')
  await pk.getByLabel('Contenido del envase 1').fill('1000')
  await pk.getByRole('button', { name: 'Guardar envases' }).click()
  await expect(pk).toBeHidden()
  await expect(row.getByTestId('stock-packages')).toHaveText('4 × Sachet 1 L + 730 ml')

  // Descartar 2 envases (vencidos)
  await row.getByRole('button', { name: `Descartar ${name}` }).click()
  const d = page.getByRole('dialog', { name: `Descartar ${name}` })
  await expect(d).toContainText('4 × Sachet 1 L + 730 ml')
  await d.getByRole('radio', { name: 'Envases' }).click()
  await d.getByLabel('Envases', { exact: true }).fill('2')
  await d.getByRole('radio', { name: 'Vencido' }).click()
  await expect(d).toContainText('Se descartan 2 L')
  await d.getByRole('button', { name: 'Descartar', exact: true }).click()
  await expect(d).toBeHidden()
  await expect(row.getByTestId('stock-packages')).toHaveText('2 × Sachet 1 L + 730 ml')

  // "Otro" needs a note; then discard everything left.
  await row.getByRole('button', { name: `Descartar ${name}` }).click()
  await d.getByRole('radio', { name: 'Todo' }).click()
  await d.getByRole('radio', { name: 'Otro' }).click()
  await expect(d.getByRole('button', { name: 'Descartar', exact: true })).toBeDisabled()
  await d.getByLabel('Detalle').fill('Se cortó la luz toda la noche')
  await d.getByRole('button', { name: 'Descartar', exact: true }).click()
  await expect(d).toBeHidden()
  await expect(row).toContainText('0 ml')

  const items: { name: string; current_qty: number }[] = await (await request.get('/api/stock/items', { headers })).json()
  expect(items.find((i) => i.name === name)!.current_qty).toBe(0)
})

test('quick discard of a small spill from the POS', async ({ page, request }) => {
  const headers = await authHeaders(page)
  const name = `Crema ${uid()}`
  const res = await request.post('/api/stock/items', { headers, data: { name, unit: 'ml', initial_qty: 500 } })
  const item = await res.json()
  await openPos(page)
  await page.getByRole('button', { name: 'Descartar insumo' }).click()
  const d = page.getByRole('dialog', { name: 'Descartar insumo' })
  await d.getByLabel('Insumo').click()
  await page.getByRole('option', { name }).click()
  await d.getByRole('button', { name: '10 ml' }).click()
  await d.getByRole('button', { name: 'Descartar', exact: true }).click()
  await expect(d).toBeHidden()
  const after = await (await request.get(`/api/stock/items/${item.id}`, { headers })).json()
  expect(after.current_qty).toBe(490)
})
