import type { Page } from '@playwright/test'

import { expect, test } from './fixtures'
import { uid, withFreePlan } from './helpers'

const main = (page: Page) => page.getByRole('main').last()
const saveButton = (page: Page) => main(page).getByRole('button', { name: 'Guardar' }).first()

/** Sets a numeric/text field on a settings tab and saves it (no-op when it already has that value). */
async function setAndSave(page: Page, tab: string, label: string, value: string, toast: string) {
  await page.goto(`/config?tab=${tab}`)
  const field = main(page).getByLabel(label)
  await expect(field).toBeVisible()
  if ((await field.inputValue()) === value) return
  await field.fill(value)
  await saveButton(page).click()
  await expect(page.getByText(toast)).toBeVisible()
}

test.describe('Configuración', () => {
  test('business data saves and persists', async ({ page }) => {
    const address = `Calle Falsa ${uid()}`
    try {
      await setAndSave(page, 'negocio', 'Dirección', address, 'Datos del negocio guardados')
      await page.reload()
      await expect(main(page).getByLabel('Dirección')).toHaveValue(address)
      await expect(saveButton(page)).toBeDisabled() // nothing dirty
    } finally {
      await setAndSave(page, 'negocio', 'Dirección', '', 'Datos del negocio guardados')
    }
  })

  test('users: create, reset PIN, deactivate', async ({ page }) => {
    const name = `Usuario ${uid()}`
    await page.goto('/config?tab=usuarios')
    await main(page).getByRole('button', { name: 'Nuevo usuario' }).click()
    const dlg = page.getByRole('dialog', { name: 'Nuevo usuario' })
    await dlg.getByLabel('Nombre').fill(name)
    await dlg.getByRole('combobox').click()
    await page.getByRole('option', { name: 'Barista' }).click()
    await dlg.getByLabel('PIN', { exact: true }).fill('4321')
    await dlg.getByLabel('Repetí el PIN').fill('4320')
    await expect(dlg.getByText('Los PIN no coinciden.')).toBeVisible()
    await expect(dlg.getByRole('button', { name: 'Crear usuario' })).toBeDisabled()
    await dlg.getByLabel('Repetí el PIN').fill('4321')
    await dlg.getByRole('button', { name: 'Crear usuario' }).click()
    await expect(page.getByText(`Usuario ${name} creado`)).toBeVisible()

    const row = main(page).getByRole('row').filter({ hasText: name })
    await expect(row).toContainText('Barista')
    await expect(row).toContainText('Nunca ingresó')

    await row.getByRole('button', { name: 'PIN' }).click()
    const pin = page.getByRole('dialog', { name: 'Restablecer PIN' })
    await pin.getByLabel('PIN', { exact: true }).fill('5678')
    await pin.getByLabel('Repetí el PIN').fill('5678')
    await pin.getByRole('button', { name: 'Guardar' }).click()
    await expect(page.getByText(`PIN de ${name} actualizado`)).toBeVisible()

    await row.getByRole('switch', { name: 'Desactivar' }).click()
    await expect(page.getByText(`${name} desactivado`)).toBeVisible()
    await expect(row.getByRole('switch')).toHaveAttribute('aria-checked', 'false')
    // Deactivated users don't show on the PIN screen
    const users: { name: string }[] = await (await page.request.get('/api/auth/users')).json()
    expect(users.map((u) => u.name)).not.toContain(name)
  })

  test('free plan refuses another user with a Pro message', async ({ page, request }) => {
    await page.goto('/config?tab=usuarios')
    await withFreePlan(page, request, async () => {
      await page.reload()
      await main(page).getByRole('button', { name: 'Nuevo usuario' }).click()
      const dlg = page.getByRole('dialog', { name: 'Nuevo usuario' })
      await dlg.getByLabel('Nombre').fill(`Extra ${uid()}`)
      await dlg.getByLabel('PIN', { exact: true }).fill('4444')
      await dlg.getByLabel('Repetí el PIN').fill('4444')
      await dlg.getByRole('button', { name: 'Crear usuario' }).click()
      await expect(page.getByText(/El plan gratuito permite 2 usuarios\. Con .* Pro son ilimitados\./)).toBeVisible()
      await expect(dlg).toBeVisible() // stays open
    })
    await page.goto('/config?tab=licencia')
    await expect(page.getByText('licencia perpetua')).toBeVisible()
  })

  test('loyalty, alerts and security settings save', async ({ page }) => {
    try {
      // Fidelización: the live summary follows the values
      await page.goto('/config?tab=fidelizacion')
      await main(page).getByLabel('Pesos por punto').fill('500')
      await expect(main(page).getByText(/acumula 100 puntos/)).toBeVisible()
      await saveButton(page).click()
      await expect(page.getByText('Fidelización guardada')).toBeVisible()

      // Alertas: invalid combination blocks saving
      await page.goto('/config?tab=alertas')
      await main(page).getByLabel('Café: reposo mínimo').fill('40')
      await expect(main(page).getByText(/el reposo mínimo tiene que ser menor/)).toBeVisible()
      await expect(saveButton(page)).toBeDisabled()
      await main(page).getByLabel('Café: reposo mínimo').fill('5')
      await setAndSave(page, 'alertas', 'Vencimiento de insumos', '7', 'Umbrales de alertas guardados')

      // Seguridad
      await setAndSave(page, 'seguridad', 'Minutos de inactividad', '15', 'Tiempo de bloqueo guardado')
      await page.reload()
      await expect(main(page).getByLabel('Minutos de inactividad')).toHaveValue('15')
      await expect(main(page).getByText('Registro de actividad')).toBeVisible()
    } finally {
      await setAndSave(page, 'fidelizacion', 'Pesos por punto', '1000', 'Fidelización guardada')
      await setAndSave(page, 'alertas', 'Vencimiento de insumos', '5', 'Umbrales de alertas guardados')
      await setAndSave(page, 'seguridad', 'Minutos de inactividad', '10', 'Tiempo de bloqueo guardado')
    }
  })

  test('backup: create one; restore asks for confirmation', async ({ page }) => {
    await page.goto('/config?tab=respaldo')
    const table = main(page).locator('[data-slot="card"]').filter({ hasText: 'Copias completas' })
    const manualRows = table.getByRole('row').filter({ hasText: 'Manual' })
    const before = await manualRows.count()
    await main(page).getByRole('button', { name: 'Crear respaldo ahora' }).click()
    await expect(page.getByText('Respaldo creado')).toBeVisible()
    await expect(manualRows).toHaveCount(before + 1)

    await manualRows.first().getByRole('button', { name: 'Restaurar' }).click()
    const confirm = page.getByRole('alertdialog', { name: '¿Restaurar este respaldo?' })
    await expect(confirm.getByText('todos los datos actuales')).toBeVisible()
    await confirm.getByRole('button', { name: 'Cancelar' }).click()
    await expect(confirm).toBeHidden()
  })

  test('appearance, about and license tabs', async ({ page, errors }) => {
    await page.goto('/config?tab=apariencia')
    const html = page.locator('html')
    await main(page).getByRole('radio', { name: /Oscuro/ }).click()
    await expect(html).toHaveClass(/dark/)
    await main(page).getByRole('radio', { name: /Claro/ }).click()
    await expect(html).not.toHaveClass(/dark/)
    await expect(main(page).getByRole('radio', { name: /Claro/ })).toHaveAttribute('aria-checked', 'true')

    await main(page).getByRole('tab', { name: 'Acerca de' }).click()
    await expect(main(page).getByText('Licencia MIT')).toBeVisible()
    await expect(main(page).getByText(/Versión \d/)).toBeVisible()

    await main(page).getByRole('tab', { name: 'Licencia' }).click()
    await expect(page.getByText('licencia perpetua')).toBeVisible()

    for (const tab of ['Negocio', 'Usuarios', 'Medios de pago', 'Fidelización', 'Alertas', 'Seguridad', 'Respaldo']) {
      await main(page).getByRole('tab', { name: tab, exact: true }).click()
      await expect(main(page).getByRole('tab', { name: tab, exact: true })).toHaveAttribute('aria-selected', 'true')
    }
    expect(errors.consoleErrors).toEqual([])
  })
})
