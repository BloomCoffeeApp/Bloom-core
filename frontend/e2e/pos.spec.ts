import { addMedialuna, ensureCashOpen, expect, test } from './fixtures'

test('sell a product in cash', async ({ page, errors }) => {
  await page.goto('/pos')
  await ensureCashOpen(page)

  await addMedialuna(page)
  await page.getByRole('button', { name: /COBRAR/ }).click()

  const dialog = page.getByRole('dialog', { name: 'Cobrar' })
  await expect(dialog.getByRole('button', { name: 'Efectivo' })).toBeVisible()
  await dialog.getByRole('button', { name: /Confirmar cobro/ }).click()

  await expect(page.getByRole('dialog').getByText('¡Venta cobrada!')).toBeVisible()
  expect(errors.consoleErrors).toEqual([])
})
