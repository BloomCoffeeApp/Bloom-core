import { USERS } from './constants'
import { expect, loginWithPin, test } from './fixtures'

// A fresh browser (no saved session, no "tour done" flag) so the tour auto-opens.
test.use({ storageState: { cookies: [], origins: [] } })

test('tour auto-opens on first login, closes with Esc and reopens from the header', async ({ page }) => {
  await loginWithPin(page, USERS.encargado.name, USERS.encargado.pin)

  const tour = page.getByRole('dialog').filter({ hasText: /Paso \d+ de \d+/ })
  await expect(tour).toBeVisible()
  await expect(tour).toContainText('Paso 1 de')

  await page.keyboard.press('Escape')
  await expect(tour).toBeHidden()

  await page.getByRole('button', { name: 'Ver tutorial' }).click()
  await expect(tour).toContainText('Paso 1 de')
  await page.keyboard.press('ArrowRight')
  await expect(tour).toContainText('Paso 2 de')
  await page.keyboard.press('ArrowLeft')
  await expect(tour).toContainText('Paso 1 de')

  await tour.getByRole('button', { name: 'Saltar' }).click()
  await expect(tour).toBeHidden()

  // Finished once: it doesn't auto-open again after a reload.
  await page.reload()
  await expect(page.getByRole('button', { name: 'Ver tutorial' })).toBeVisible()
  await page.waitForTimeout(1_500) // the auto-start waits 800 ms
  await expect(tour).toBeHidden()
})
