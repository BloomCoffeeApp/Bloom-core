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
