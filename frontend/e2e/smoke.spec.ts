import { expect, test } from './fixtures'

const ROUTES: { path: string; heading: string | RegExp }[] = [
  { path: '/', heading: /Admin/ },
  { path: '/caja', heading: 'Caja' },
  { path: '/ventas', heading: 'Ventas' },
  { path: '/productos', heading: 'Productos' },
  { path: '/stock', heading: 'Stock' },
  { path: '/clientes', heading: 'Clientes' },
  { path: '/avisos', heading: 'Avisos' },
  { path: '/config', heading: 'Configuración' },
]

test.describe('smoke: every main route renders without errors', () => {
  for (const { path, heading } of ROUTES) {
    test(path, async ({ page, errors }) => {
      await page.goto(path)
      await expect(page.getByRole('heading', { level: 1, name: heading })).toBeVisible()
      await page.waitForLoadState('networkidle')
      expect(errors.consoleErrors).toEqual([])
    })
  }

  // Full-bleed POS screen: no page header, the search box and checkout button are the landmarks.
  test('/pos', async ({ page, errors }) => {
    await page.goto('/pos')
    await expect(page.getByRole('button', { name: /COBRAR/ })).toBeVisible()
    await expect(page.getByRole('textbox', { name: 'Buscar producto' })).toBeVisible()
    await page.waitForLoadState('networkidle')
    expect(errors.consoleErrors).toEqual([])
  })
})
