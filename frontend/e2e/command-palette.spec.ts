import { expect, test } from './fixtures'

const PLACEHOLDER = 'Escribí una sección o acción…'

// Regression: choosing an entry used to render a blank screen.
test('Ctrl+K opens the palette and Enter navigates', async ({ page, errors }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()

  await page.keyboard.press('Control+k')
  const input = page.getByPlaceholder(PLACEHOLDER)
  await expect(input).toBeVisible()
  await input.fill('stock')
  await page.keyboard.press('Enter')

  await expect(page).toHaveURL(/\/stock$/)
  await expect(page.getByRole('heading', { level: 1, name: 'Stock' })).toBeVisible()
  await expect(input).toBeHidden()
  expect(errors.consoleErrors).toEqual([])
})

test('the header search button opens the palette too', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: /Buscar o ir a/ }).click()
  await page.getByPlaceholder(PLACEHOLDER).fill('clientes')
  await page.getByRole('option', { name: 'Clientes', exact: true }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Clientes' })).toBeVisible()
})
