import { expect, test } from './fixtures'
import { e2eProLicense } from './license'

test('license tab shows Pro; going Free shows the upgrade card; re-importing restores it', async ({ page, request }) => {
  await page.goto('/config?tab=licencia')
  const token = await page.evaluate(() => localStorage.getItem('cafe.token'))
  const auth = { Authorization: `Bearer ${token}` }
  await expect(page.getByText('licencia perpetua')).toBeVisible()

  try {
    await request.delete('/api/license', { headers: auth })
    await page.goto('/reportes')
    await expect(page.getByRole('heading', { name: 'Reportes avanzados' })).toBeVisible()
    await expect(page.getByRole('link', { name: /Activar .* Pro/ })).toBeVisible()
    // Core keeps working on Free
    await page.goto('/pos')
    await expect(page.getByText('COBRAR')).toBeVisible()
    // Pro badge in the menu
    await expect(page.locator('[data-tour="nav-/compras"]').locator('..').getByText('Pro')).toBeVisible()
  } finally {
    const res = await request.post('/api/license/import', { data: { token: e2eProLicense() }, headers: auth })
    expect(res.ok()).toBeTruthy()
  }
  await page.goto('/config?tab=licencia')
  await expect(page.getByText('licencia perpetua')).toBeVisible()
})

test('when the Pro trial ends: one dialog to subscribe or stay free, then it never nags again', async ({ page }) => {
  // Simulate a PC whose trial just ran out (the e2e stack can't wait 7 days).
  await page.route('**/api/license', async (route) => {
    const res = await route.fetch()
    const body = await res.json()
    await route.fulfill({
      response: res,
      json: { ...body, plan: 'free', valid: false, features: [], trial_ended: true, license_id: 'trial-e2e', problem: 'Terminó la prueba gratuita.' },
    })
  })
  await page.goto('/')
  const dialog = page.getByRole('dialog', { name: /Terminó tu prueba de .* Pro/ })
  await expect(dialog).toBeVisible()
  await expect(dialog).toContainText('Tus datos quedan intactos')
  await expect(dialog.getByRole('button', { name: 'Suscribirme a Pro' })).toBeVisible()
  await dialog.getByRole('button', { name: 'Seguir con el plan gratis' }).click()
  await expect(dialog).toBeHidden()
  await expect(page.getByText('Terminó la prueba gratuita.')).toHaveCount(0) // no permanent alarm banner
  await page.reload()
  await expect(page.getByRole('heading', { level: 1 }).first()).toBeVisible()
  await expect(dialog).toHaveCount(0)
})

test('the last days of the trial show a heads-up', async ({ page }) => {
  await page.route('**/api/license', async (route) => {
    const res = await route.fetch()
    const body = await res.json()
    await route.fulfill({ response: res, json: { ...body, plan: 'trial', valid: true, perpetual: false, days_left: 1, in_grace: false } })
  })
  await page.goto('/')
  await expect(page.getByText(/Mañana termina tu prueba de .* Pro/)).toBeVisible()
})
