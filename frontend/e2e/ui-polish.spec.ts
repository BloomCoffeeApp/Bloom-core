import { expect, test } from './fixtures'
import { pickDate, uid } from './helpers'

test.describe('UI polish: notifications popup, number and date fields', () => {
  test('the bell opens a popup with «Ahora» and alerts, and «Ver todas» goes to Avisos', async ({ page, errors }) => {
    await page.route('**/api/notifications/urgent', (route) =>
      route.fulfill({
        json: {
          total: 2,
          items: [
            { key: 'order:1', kind: 'online_order', title: 'Pedido online nuevo #7', detail: 'Esperando que lo aceptes', at: new Date().toISOString(), to: '/pedidos' },
            { key: 'call:3', kind: 'call_bill', title: 'Mesa 4: pidió la cuenta', detail: null, at: new Date().toISOString(), to: '/pedidos' },
          ],
        },
      }),
    )
    await page.goto('/')
    await page.getByRole('button', { name: /^Notificaciones/ }).click()
    const pop = page.getByTestId('notifications-popover')
    await expect(pop.getByText('Notificaciones', { exact: true })).toBeVisible()
    await expect(pop.getByText('Ahora', { exact: true })).toBeVisible()
    await expect(pop.getByText('Pedido online nuevo #7')).toBeVisible()
    await expect(pop.getByText('Mesa 4: pidió la cuenta')).toBeVisible()

    // An item takes you to Pedidos and closes the popup.
    await pop.getByText('Pedido online nuevo #7').click()
    await expect(page).toHaveURL(/\/pedidos/)
    await expect(pop).toBeHidden()

    await page.getByRole('button', { name: /^Notificaciones/ }).click()
    await page.getByTestId('notifications-popover').getByRole('link', { name: 'Ver todas' }).click()
    await expect(page).toHaveURL(/\/avisos/)
    expect(errors.consoleErrors).toEqual([])
  })

  test('with nothing pending the popup says everything is in order', async ({ page, errors }) => {
    await page.route('**/api/notifications/urgent', (route) => route.fulfill({ json: { total: 0, items: [] } }))
    await page.route('**/api/alerts?*', (route) => route.fulfill({ json: [] }))
    await page.goto('/')
    await page.getByRole('button', { name: /^Notificaciones/ }).click()
    await expect(page.getByTestId('notifications-popover').getByText('Todo en orden. No hay nada pendiente.')).toBeVisible()
    expect(errors.consoleErrors).toEqual([])
  })

  test('number fields have no browser spin arrows', async ({ page }) => {
    await page.goto('/')
    const appearance = await page.evaluate(() => {
      const input = document.createElement('input')
      input.type = 'number'
      document.body.append(input)
      const value = getComputedStyle(input).getPropertyValue('appearance')
      input.remove()
      return value
    })
    expect(appearance).toBe('textfield')
  })

  test('the date picker: Spanish calendar, keyboard and Esc', async ({ page, errors }) => {
    await page.goto('/ventas')
    await page.getByRole('button', { name: 'Rango', exact: true }).click()
    const from = page.getByLabel('Desde')
    await from.click()
    const pop = page.getByTestId('date-picker-popover')
    await expect(pop).toBeVisible()
    await expect(pop.getByRole('grid')).toHaveAttribute('aria-label', /^[a-zé]+ de \d{4}$/)

    // Keyboard: the focused day moves with the arrows and Enter picks it.
    const focused = await pop.locator('[data-day][tabindex="0"]').getAttribute('data-day')
    await page.keyboard.press('ArrowLeft')
    const moved = await pop.locator('[data-day][tabindex="0"]').getAttribute('data-day')
    expect(moved).not.toBe(focused)
    await page.keyboard.press('Enter')
    await expect(pop).toBeHidden()
    await expect(from).toHaveAttribute('data-value', moved!)

    // Esc closes it without changing the value.
    await from.click()
    await page.keyboard.press('Escape')
    await expect(pop).toBeHidden()
    await expect(from).toHaveAttribute('data-value', moved!)
    expect(errors.consoleErrors).toEqual([])
  })

  test('pickDate walks to another month and year (a gasto due date)', async ({ page, errors }) => {
    await page.goto('/gastos')
    await page.getByRole('button', { name: 'Nuevo gasto' }).click()
    const form = page.getByRole('dialog', { name: 'Nuevo gasto' })
    await form.getByRole('radio', { name: 'Pendiente de pago' }).click()
    await pickDate(form, 'Vence el', '2031-02-14')
    await expect(form.getByLabel('Vence el')).toHaveAttribute('data-value', '2031-02-14')
    await expect(form.getByLabel('Vence el')).toContainText('14 de feb 2031')
    expect(errors.consoleErrors).toEqual([])
  })

  test('a birthday without a year is saved and shows no age', async ({ page, errors }) => {
    const name = `Sin año ${uid()}`
    await page.goto('/clientes')
    await page.getByRole('button', { name: 'Nuevo cliente' }).click()
    const form = page.getByRole('dialog', { name: 'Nuevo cliente' })
    await form.getByLabel('Nombre').fill(name)
    await form.getByRole('combobox', { name: 'Día' }).click()
    await page.getByRole('option', { name: '3', exact: true }).click()
    await form.getByRole('combobox', { name: 'Mes' }).click()
    await page.getByRole('option', { name: 'octubre' }).click()
    await expect(form.getByRole('combobox', { name: 'Año (opcional)' })).toContainText('Sin año')
    await form.getByRole('button', { name: 'Guardar' }).click()
    await expect(page).toHaveURL(/\/clientes\/\d+$/)
    await expect(page.getByText('03/10', { exact: true })).toBeVisible()
    await expect(page.getByText(/\d+ años/)).toHaveCount(0)
    expect(errors.consoleErrors).toEqual([])
  })
})
