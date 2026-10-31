import { ADMIN, USERS } from './constants'
import { enterPin, expect, test } from './fixtures'

test.use({ storageState: { cookies: [], origins: [] } })

test.describe('login', () => {
  test('shows the user picker', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByText('¿Quién está trabajando?')).toBeVisible()
    for (const name of [ADMIN.name, USERS.caja.name, USERS.barista.name, USERS.encargado.name])
      await expect(page.getByRole('button', { name: new RegExp(name) })).toBeVisible()
  })

  test('wrong PIN shows an error, the right one enters', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('button', { name: new RegExp(USERS.barista.name) }).click()
    await expect(page.getByText('Hola Barista, ingresá tu PIN')).toBeVisible()

    await enterPin(page, '9876')
    await expect(page.getByText('PIN incorrecto')).toBeVisible()

    await enterPin(page, USERS.barista.pin)
    await expect(page.getByRole('button', { name: 'Ver tutorial' })).toBeVisible()
    await expect(page.getByText('¿Quién está trabajando?')).toBeHidden()
  })

  // Regression: the PIN pad's spacer used to share key `9` with the "9" button.
  test('the PIN pad renders without console errors', async ({ page, errors }) => {
    await page.goto('/')
    await page.getByRole('button', { name: new RegExp(USERS.barista.name) }).click()
    await expect(page.getByRole('button', { name: 'Entrar' })).toBeVisible()
    expect(errors.consoleErrors).toEqual([])
  })

  test('the physical keyboard works on the PIN pad', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('button', { name: new RegExp(USERS.barista.name) }).click()
    await expect(page.getByText('Hola Barista, ingresá tu PIN')).toBeVisible()
    await page.keyboard.type(USERS.barista.pin)
    await page.keyboard.press('Enter')
    await expect(page.getByRole('button', { name: 'Ver tutorial' })).toBeVisible()
  })
})
