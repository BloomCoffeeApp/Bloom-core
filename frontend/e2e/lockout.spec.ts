import { USERS } from './constants'
import { enterPin, expect, test } from './fixtures'

// Runs in its own project, after everything else: the throttle also locks this device (IP),
// so no further PIN logins work for a while.
test.use({ storageState: { cookies: [], origins: [] } })

test('5 wrong PINs lock the login', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: new RegExp(USERS.caja.name) }).click()
  for (let i = 0; i < 5; i++) {
    await enterPin(page, '9999')
    await expect(page.getByText('PIN incorrecto')).toBeVisible()
  }
  await enterPin(page, '9999')
  await expect(page.getByText(/Demasiados intentos fallidos\. Probá de nuevo en \d+ segundos/)).toBeVisible()

  // Even the right PIN is rejected while locked.
  await enterPin(page, USERS.caja.pin)
  await expect(page.getByText(/Demasiados intentos fallidos/)).toBeVisible()
  await expect(page.getByRole('button', { name: 'Entrar' })).toBeVisible()
})
