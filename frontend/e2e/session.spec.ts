import { USERS } from './constants'
import { expect, test } from './fixtures'
import { freshLogin } from './helpers'

// Locking revokes the session token, so these use their own login instead of the shared admin session.
test.use({ storageState: { cookies: [], origins: [] } })

test('the lock button returns to the user picker', async ({ page }) => {
  await freshLogin(page, USERS.caja.name, USERS.caja.pin)
  await page.getByRole('button', { name: 'Bloquear' }).click()
  await expect(page.getByText('¿Quién está trabajando?')).toBeVisible()
  await page.reload() // the token is gone, not just the UI state
  await expect(page.getByText('¿Quién está trabajando?')).toBeVisible()
})

test('a failed request at startup does not throw the session away (only a 401 does)', async ({ page }) => {
  await freshLogin(page, USERS.caja.name, USERS.caja.pin)
  await page.route('**/api/auth/me', (r) => r.abort())
  await page.reload()
  // The app could not check the session this time, but the token is still there…
  expect(await page.evaluate(() => localStorage.getItem('cafe.token'))).toBeTruthy()
  // …so as soon as the server answers again the person is back in without typing the PIN.
  await page.unroute('**/api/auth/me')
  await page.reload()
  await expect(page.getByRole('button', { name: 'Bloquear' })).toBeVisible()
})

test('idle lock after the configured minutes without activity', async ({ page }) => {
  await page.clock.install()
  await freshLogin(page, USERS.encargado.name, USERS.encargado.pin)
  await page.goto('/stock')
  await expect(page.getByRole('heading', { level: 1, name: 'Stock' })).toBeVisible()

  // Default: 10 minutes. Activity resets the timer.
  await page.clock.fastForward('08:00')
  await page.keyboard.press('Shift')
  await page.clock.fastForward('08:00')
  await expect(page.getByRole('heading', { level: 1, name: 'Stock' })).toBeVisible()

  await page.clock.fastForward('03:00')
  // Past the idle limit the session is closed (token revoked and removed)…
  await expect.poll(() => page.evaluate(() => localStorage.getItem('cafe.token'))).toBeNull()
  // …and the PIN screen shows. (Rendering it under the fake clock is timing-sensitive, so check
  // it with time flowing normally.)
  await page.clock.resume()
  await page.reload()
  await expect(page.getByText('¿Quién está trabajando?')).toBeVisible()
})
