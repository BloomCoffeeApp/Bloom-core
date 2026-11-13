import { ensureCashOpen, expect, test } from './fixtures'
import { scan } from './a11y-scan'

const ROUTES = ['/', '/caja', '/ventas', '/productos', '/stock', '/clientes', '/avisos', '/config', '/pos']

test.describe('accessibility: main screens', () => {
  for (const path of ROUTES) {
    test(`light ${path}`, async ({ page }) => {
      await page.emulateMedia({ colorScheme: 'light' })
      await page.goto(path)
      await page.waitForLoadState('networkidle')
      expect(await scan(page)).toEqual([])
    })
  }

  test('dark /pos and /', async ({ page }) => {
    await page.emulateMedia({ colorScheme: 'dark' })
    await page.addInitScript(() => localStorage.setItem('cafe.theme', 'dark'))
    for (const path of ['/', '/pos']) {
      await page.goto(path)
      await page.waitForLoadState('networkidle')
      expect(await scan(page), `dark ${path}`).toEqual([])
    }
  })

  test('POS checkout dialog', async ({ page }) => {
    await page.goto('/pos')
    await ensureCashOpen(page)
    await page.getByRole('button', { name: /Medialuna/ }).first().click()
    await page.getByRole('button', { name: /COBRAR/ }).click()
    await expect(page.getByRole('dialog', { name: 'Cobrar' })).toBeVisible()
    expect(await scan(page)).toEqual([])
  })
})
