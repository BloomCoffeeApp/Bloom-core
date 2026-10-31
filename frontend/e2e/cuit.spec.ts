import { expect, test } from './fixtures'

test('CUIT mask in Configuración → Negocio', async ({ page }) => {
  await page.goto('/config?tab=negocio')
  const cuit = page.getByLabel('CUIT')
  await cuit.clear()
  await cuit.pressSequentially('20123456789')
  await expect(cuit).toHaveValue('20-12345678-9')
})
