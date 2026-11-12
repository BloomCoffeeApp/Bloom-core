import path from 'node:path'

import type { Page } from '@playwright/test'

import { expect, test } from './fixtures'
import { authHeaders, cartLine, confirmCheckout, money, openCheckout, openPos, productTile, ticketNumber, uid } from './helpers'

/** Optional: SHOTS_DIR=<folder> saves review screenshots of the new screens. */
const SHOTS = process.env.SHOTS_DIR

async function shot(page: Page, name: string, scheme: 'light' | 'dark' = 'light') {
  if (!SHOTS) return
  await page.emulateMedia({ colorScheme: scheme })
  await page.waitForTimeout(250)
  await page.screenshot({ path: path.join(SHOTS, `${name}-${scheme}.png`) })
}

test('sizes: define them, price a product per size and sell a Grande in the POS', async ({ page, request, errors }) => {
  const id = uid()
  const chico = `Chico ${id}`
  const grande = `Grande ${id}`
  const product = `Latte tamaños ${id}`
  const headers = await authHeaders(page)

  // A latte-like product (200 ml milk + 18 g coffee) to give sizes to.
  const items: { id: number; name: string; current_qty: number }[] = await (await request.get('/api/stock/items', { headers })).json()
  const milk = items.find((i) => i.name === 'Leche entera')!
  const coffee = items.find((i) => i.name === 'Café blend de la casa')!
  const created = await request.post('/api/products', {
    headers,
    data: {
      name: product,
      price_cents: 340_000,
      recipe_items: [
        { stock_item_id: milk.id, qty: 200 },
        { stock_item_id: coffee.id, qty: 18 },
      ],
    },
  })
  expect(created.ok(), await created.text()).toBeTruthy()

  // 1) Sizes tab: create two sizes.
  await page.goto('/productos?tab=tamanos')
  for (const [name, label, ml] of [
    [chico, 'Ch', '240'],
    [grande, 'Gr', '480'],
  ]) {
    await page.getByRole('button', { name: 'Nuevo tamaño' }).click()
    const dlg = page.getByRole('dialog', { name: 'Nuevo tamaño' })
    await dlg.getByLabel('Nombre').fill(name)
    await dlg.getByLabel('Abreviatura').fill(label)
    await dlg.getByLabel('Volumen en ml (opcional)').fill(ml)
    await dlg.getByRole('button', { name: 'Guardar', exact: true }).click()
    await expect(dlg).toBeHidden()
    await expect(page.getByTestId('size-card').filter({ hasText: name })).toContainText(`${ml} ml`)
  }

  // 2) Product editor: sold in Chico ($3.000) and Grande ($4.200, recipe ×1.5).
  await page.goto('/productos')
  await page.getByPlaceholder('Buscar producto…').fill(product)
  await page.getByRole('row').filter({ hasText: product }).click()
  const editor = page.getByRole('dialog', { name: product })
  await editor.getByRole('switch', { name: 'Se vende en distintos tamaños' }).click()
  await editor.getByRole('checkbox', { name: `Vender en ${chico}` }).click()
  await editor.getByLabel(`Precio ${chico}`).fill('3000')
  await editor.getByLabel(`Factor de receta ${chico}`).fill('0,75')
  await editor.getByRole('checkbox', { name: `Vender en ${grande}` }).click()
  await editor.getByLabel(`Precio ${grande}`).fill('4200')
  await editor.getByRole('button', { name: 'Escalar por volumen' }).click()
  await expect(editor.getByLabel(`Factor de receta ${grande}`)).toHaveValue('1.5')
  await editor.getByRole('button', { name: `Receta de ${grande}` }).click()
  await expect(editor.getByLabel(`Cantidad de Leche entera en ${grande}`)).toHaveValue('300')
  await editor.getByRole('heading', { name: 'Tamaños', exact: true }).scrollIntoViewIfNeeded()
  await shot(page, 'product-editor-sizes')
  await shot(page, 'product-editor-sizes', 'dark')
  await page.emulateMedia({ colorScheme: 'light' })
  await editor.getByRole('button', { name: 'Guardar', exact: true }).click()
  await expect(editor).toBeHidden()
  const row = page.getByRole('row').filter({ hasText: product })
  await expect(row).toContainText(`${money(300_000)} – ${money(420_000)}`)
  await expect(row).toContainText('Ch/Gr')

  // 3) POS: the size picker (default = first), choose Grande.
  await openPos(page)
  await productTile(page, product).click()
  const picker = page.getByRole('dialog', { name: product })
  const sizes = picker.getByRole('radiogroup', { name: 'Tamaño' })
  await expect(sizes.getByRole('radio')).toHaveCount(2)
  await expect(sizes.getByRole('radio', { name: new RegExp(chico) })).toHaveAttribute('aria-checked', 'true')
  const grandeBtn = sizes.getByRole('radio', { name: new RegExp(grande) })
  const box = (await grandeBtn.boundingBox())!
  expect(box.height).toBeGreaterThanOrEqual(44)
  await grandeBtn.click()
  await expect(grandeBtn).toHaveAttribute('aria-checked', 'true')
  await shot(page, 'pos-size-picker')
  await shot(page, 'pos-size-picker', 'dark')
  await page.emulateMedia({ colorScheme: 'light' })
  await picker.getByRole('button', { name: `Agregar · ${money(420_000)}` }).click()
  await expect(cartLine(page, product).first()).toContainText('Gr')

  const dialog = await openCheckout(page)
  await expect(dialog).toContainText(money(420_000))
  const n = await ticketNumber(await confirmCheckout(page, dialog))

  // Stock went down by the Grande recipe (300 ml milk, 27 g coffee).
  const after: { id: number; current_qty: number }[] = await (await request.get('/api/stock/items', { headers })).json()
  expect(after.find((i) => i.id === milk.id)!.current_qty).toBeCloseTo(milk.current_qty - 300, 3)
  expect(after.find((i) => i.id === coffee.id)!.current_qty).toBeCloseTo(coffee.current_qty - 27, 3)

  // 4) Sales detail shows the size and its price at the time of sale.
  await page.keyboard.press('Escape')
  await page.goto('/ventas')
  await page.getByPlaceholder('N° de ticket').fill(String(n))
  await page.getByRole('row').filter({ hasText: `#${n}` }).click()
  const sheet = page.getByRole('dialog', { name: new RegExp(`Ticket #${n}`) })
  await expect(sheet.getByText(product)).toBeVisible()
  await expect(sheet.getByText(grande)).toBeVisible()
  await expect(sheet).toContainText(money(420_000))
  expect(errors.consoleErrors).toEqual([])
})
