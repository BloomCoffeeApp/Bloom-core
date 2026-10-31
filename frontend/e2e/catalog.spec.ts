import { expect, test } from './fixtures'
import { authHeaders, money, productTile, uid } from './helpers'

test('category, modifier group and product with recipe: price edit, bulk increase, deactivate', async ({ page, request, errors }) => {
  test.setTimeout(90_000)
  const id = uid()
  const cat = `Cat ${id}`
  const group = `Grupo ${id}`
  const product = `Prod ${id}`

  // Category
  await page.goto('/productos?tab=categorias')
  await page.getByRole('button', { name: 'Nueva categoría' }).click()
  const catDlg = page.getByRole('dialog', { name: 'Nueva categoría' })
  await catDlg.getByLabel('Nombre').fill(cat)
  await catDlg.getByRole('button', { name: 'Guardar' }).click()
  await expect(catDlg).toBeHidden()
  await expect(page.getByText(cat, { exact: true })).toBeVisible()

  // Modifier group
  await page.getByRole('tab', { name: 'Modificadores' }).click()
  await page.getByRole('button', { name: 'Nuevo grupo' }).click()
  const grpDlg = page.getByRole('dialog', { name: 'Nuevo grupo de modificadores' })
  await grpDlg.getByLabel('Nombre', { exact: true }).fill(group)
  await grpDlg.getByPlaceholder('Nombre de la opción').fill('Opción A')
  await grpDlg.getByRole('button', { name: 'Guardar grupo' }).click()
  await expect(grpDlg).toBeHidden()
  const grpCard = page.locator('[data-slot="card"]').filter({ hasText: group })
  await expect(grpCard).toContainText('Opcional · elegir 1')

  // Product with a recipe line: cost and margin are computed live
  const items = await (await request.get('/api/stock/items', { headers: await authHeaders(page) })).json()
  const milk = items.find((i: { name: string }) => i.name === 'Leche entera')
  const lineCost = Math.round(200 * milk.avg_cost_cents)

  await page.getByRole('tab', { name: 'Productos' }).click()
  await page.getByRole('button', { name: 'Nuevo producto' }).click()
  const editor = page.getByRole('dialog', { name: 'Nuevo producto' })
  await editor.getByLabel('Nombre').fill(product)
  await editor.getByLabel('Categoría').click()
  await page.getByRole('option', { name: cat }).click()
  await editor.getByLabel('Precio de venta').fill('5000')
  await editor.getByRole('button', { name: 'Agregar insumo' }).click()
  await editor.getByRole('combobox').filter({ hasText: 'Elegí un insumo…' }).click()
  await page.getByPlaceholder('Buscar insumo…').fill('Leche entera')
  await page.getByRole('option', { name: /Leche entera/ }).click()
  await editor.getByPlaceholder('0', { exact: true }).fill('200')
  const costBox = editor.getByText('Ganancia bruta').locator('../..')
  await expect(costBox).toContainText(money(lineCost))
  await expect(costBox).toContainText(money(500_000 - lineCost))
  await expect(costBox).toContainText('%')
  await editor.getByText(group).click() // modifier group checkbox
  await editor.getByRole('button', { name: 'Guardar' }).click()
  await expect(editor).toBeHidden()

  await page.getByPlaceholder('Buscar producto…').fill(product)
  const row = page.getByRole('row').filter({ hasText: product })
  await expect(row).toContainText(money(500_000))
  await expect(row).toContainText('1 insumos')
  await expect(row).toContainText(cat)

  // Sold in the POS, with its options
  await page.goto('/pos')
  await page.getByRole('textbox', { name: 'Buscar producto' }).fill(product)
  await productTile(page, product).click()
  await expect(page.getByRole('dialog', { name: product }).getByRole('button', { name: /^Opción A/ })).toBeVisible()
  await page.keyboard.press('Escape')

  // Edit the price → price history
  await page.goto('/productos')
  await page.getByPlaceholder('Buscar producto…').fill(product)
  await row.click()
  let sheet = page.getByRole('dialog', { name: product })
  await sheet.getByLabel('Precio de venta').fill('5500')
  await sheet.getByRole('button', { name: 'Guardar' }).click()
  await expect(sheet).toBeHidden()
  await expect(row).toContainText(money(550_000))
  await row.click()
  await expect(sheet.getByText('Historial de precios')).toBeVisible()
  await expect(sheet.getByText(money(500_000), { exact: true })).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(sheet).toBeHidden()

  // Bulk increase, only this category: 5.500 + 10% = 6.050
  await page.getByRole('button', { name: 'Aumento masivo' }).click()
  const bulk = page.getByRole('dialog', { name: 'Aumento masivo de precios' })
  await bulk.getByRole('combobox').filter({ hasText: 'Todos' }).click()
  await page.getByRole('option', { name: cat }).click()
  await expect(bulk.getByLabel('Porcentaje')).toHaveValue('10')
  await bulk.getByRole('button', { name: 'Vista previa' }).click()
  await expect(bulk.getByText('1 de 1 productos cambian de precio.')).toBeVisible()
  await expect(bulk).toContainText(money(605_000))
  await bulk.getByRole('button', { name: 'Aplicar a 1 productos' }).click()
  await expect(bulk).toBeHidden()
  await expect(row).toContainText(money(605_000))

  // Deactivate
  await row.click()
  sheet = page.getByRole('dialog', { name: product })
  await sheet.getByRole('button', { name: 'Desactivar' }).click()
  await expect(sheet).toBeHidden()
  await expect(row).toHaveCount(0)
  await page.getByText('Inactivos').click()
  await expect(row.locator('.line-through')).toHaveText(product)
  expect(errors.consoleErrors).toEqual([])
})
