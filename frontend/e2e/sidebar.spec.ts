import { expect, test } from './fixtures'

test('collapsing the sidebar hides the labels and keeps the separators', async ({ page }) => {
  await page.goto('/')
  const link = page.locator('[data-tour="nav-/stock"]')
  const label = link.locator('span')
  const separators = page.locator('[data-slot="sidebar-separator"]')
  const sidebar = page.locator('[data-slot="sidebar"][data-state]')
  const toggle = page.locator('header').getByRole('button', { name: 'Toggle Sidebar' })

  await expect(label).toBeVisible()
  await expect(separators).toHaveCount(2) // Operación | Gestión | Sistema

  await toggle.click()
  await expect(sidebar).toHaveAttribute('data-state', 'collapsed')
  await expect(label).toHaveCSS('display', 'none')
  await expect(separators).toHaveCount(2)
  await expect(link).toBeVisible() // the icon stays

  await toggle.click()
  await expect(sidebar).toHaveAttribute('data-state', 'expanded')
  await expect(label).toBeVisible()
})
