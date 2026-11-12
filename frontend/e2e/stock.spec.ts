import type { Locator, Page } from '@playwright/test'

import { expect, test } from './fixtures'
import { uid } from './helpers'

async function action(page: Page, row: Locator, item: string) {
  await row.getByRole('button', { name: 'Acciones' }).click()
  await page.getByRole('menuitem', { name: item }).click()
}

test('stock item: create, low-stock, adjust, waste, physical count, suggestions, deactivate', async ({ page, errors }) => {
  test.setTimeout(90_000)
  const name = `Insumo ${uid()}`

  // Create: 5 u with a minimum of 10 → low
  await page.goto('/stock')
  await page.getByRole('button', { name: 'Nuevo insumo' }).click()
  const form = page.getByRole('dialog', { name: 'Nuevo insumo' })
  await form.getByLabel('Nombre').fill(name)
  await form.getByLabel(/Stock mínimo/).fill('10')
  await form.getByLabel(/Stock inicial/).fill('5')
  await form.getByRole('button', { name: 'Guardar' }).click()
  await expect(form).toBeHidden()

  await page.getByPlaceholder('Buscar insumo…').fill(name)
  const row = page.getByRole('row').filter({ hasText: name })
  await expect(row).toContainText('Bajo mínimo')
  await expect(row).toContainText('5 u')
  await page.getByRole('tab', { name: 'Bajos' }).click()
  await expect(row).toBeVisible()
  await page.getByRole('tab', { name: 'OK' }).click()
  await expect(row).toBeHidden()
  await page.getByRole('tab', { name: 'Todos' }).click()

  // Suggestions list it while it's under the minimum
  await page.getByRole('link', { name: 'Sugerencias de compra' }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Sugerencias de compra' })).toBeVisible()
  await expect(page.getByRole('row').filter({ hasText: name })).toContainText('Bajo mínimo')
  await page.getByRole('link', { name: 'Volver a stock' }).click()
  await page.getByPlaceholder('Buscar insumo…').fill(name)

  // Manual adjustment to the real quantity
  await action(page, row, 'Ajustar')
  const adj = page.getByRole('dialog', { name: 'Ajustar stock' })
  await adj.getByLabel(/Cantidad que hay/).fill('20')
  await adj.getByLabel('Motivo').fill('Recuento e2e')
  await expect(adj.getByText('Queda en')).toBeVisible()
  await adj.getByRole('button', { name: 'Guardar ajuste' }).click()
  await expect(adj).toBeHidden()
  await expect(row).toContainText('20 u')
  await expect(row).toContainText('OK')

  // Waste
  await action(page, row, 'Descartar (merma)')
  const waste = page.getByRole('dialog', { name: `Descartar ${name}` })
  await waste.getByLabel(/Cantidad \(u\)/).fill('2')
  await waste.getByRole('radio', { name: 'Vencido' }).click()
  await waste.getByRole('button', { name: 'Descartar', exact: true }).click()
  await expect(waste).toBeHidden()
  await expect(row).toContainText('18 u')

  // Kardex
  await row.getByText(name).click()
  const kardex = page.getByRole('dialog', { name: /Movimientos/ })
  await expect(kardex.getByText('Merma')).toBeVisible()
  await expect(kardex.getByText('Vencido')).toBeVisible()
  await expect(kardex.getByText('Recuento e2e')).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(kardex).toBeHidden()

  // Physical count: there are 15, not 18
  await page.getByRole('link', { name: 'Conteo físico' }).click()
  await page.getByRole('button', { name: 'Nuevo conteo' }).click()
  await page.getByRole('dialog', { name: 'Nuevo conteo físico' }).getByRole('button', { name: 'Empezar conteo' }).click()
  await expect(page).toHaveURL(/\/stock\/conteo\/\d+$/)
  const countRow = page.locator('div.grid').filter({ has: page.getByText(name, { exact: true }) })
  await countRow.getByRole('textbox').fill('15')
  await countRow.getByRole('textbox').press('Enter')
  await expect(countRow).toContainText('-3 u')
  await page.getByRole('button', { name: 'Aplicar conteo' }).click()
  await page.getByRole('alertdialog', { name: '¿Aplicar el conteo?' }).getByRole('button', { name: 'Aplicar' }).click()
  await expect(page.getByText('Aplicado', { exact: true })).toBeVisible()

  await page.goto('/stock')
  await page.getByPlaceholder('Buscar insumo…').fill(name)
  await expect(row).toContainText('15 u')

  // Deactivate (cleanup)
  await action(page, row, 'Desactivar')
  await page.getByRole('alertdialog', { name: '¿Desactivar insumo?' }).getByRole('button', { name: 'Desactivar' }).click()
  await expect(row).toHaveCount(0)
  expect(errors.consoleErrors).toEqual([])
})
