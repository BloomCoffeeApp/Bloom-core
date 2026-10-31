import { expect, test } from './fixtures'
import { uid } from './helpers'

test.describe('Avisos', () => {
  test('alerts: re-check and filters', async ({ page, errors }) => {
    await page.goto('/avisos')
    await page.getByRole('button', { name: 'Revisar ahora' }).click()
    await expect(page.getByRole('button', { name: 'Revisar ahora' })).toBeEnabled()
    // Either grouped alerts or the "all good" state
    await expect(page.getByText(/Críticas|Advertencias|Para tener en cuenta|Todo en orden/).first()).toBeVisible()

    for (const f of ['Sin leer', 'Leídas', 'Resueltas', 'Pendientes']) {
      await page.getByRole('radio', { name: f }).click()
      await expect(page.getByRole('radio', { name: f })).toHaveAttribute('aria-checked', 'true')
    }
    const read = page.getByRole('button', { name: 'Marcar como leída' })
    if (await read.count()) {
      const before = await read.count()
      await read.first().click()
      await expect(read).toHaveCount(before - 1)
    }
    await page.waitForLoadState('networkidle')
    expect(errors.consoleErrors).toEqual([])
  })

  test('notice board: publish pinned, unpin, delete', async ({ page }) => {
    const title = `Aviso ${uid()}`
    await page.goto('/avisos?tab=tablon')
    await page.getByRole('button', { name: 'Nuevo aviso' }).first().click()
    const form = page.getByRole('dialog', { name: 'Nuevo aviso' })
    await form.getByLabel('Título').fill(title)
    await form.getByLabel('Detalle').fill('Llega el proveedor de leche a las 10')
    await form.getByRole('button', { name: 'Celeste' }).click()
    await form.getByRole('switch').click() // Fijar arriba
    await form.getByRole('button', { name: 'Publicar' }).click()
    await expect(form).toBeHidden()

    const card = page.locator('article').filter({ hasText: title })
    await expect(card).toContainText('Llega el proveedor de leche a las 10')
    await expect(card.locator('.lucide-pin')).toBeVisible()
    // Pinned notices go first
    await expect(page.locator('article').first()).toContainText(/Aviso|Bienvenido/)

    await card.getByRole('button', { name: 'Opciones' }).click()
    await page.getByRole('menuitem', { name: 'Desfijar' }).click()
    await expect(card.locator('.lucide-pin')).toHaveCount(0)

    await card.getByRole('button', { name: 'Opciones' }).click()
    await page.getByRole('menuitem', { name: 'Eliminar' }).click()
    await page.getByRole('alertdialog', { name: '¿Eliminar este aviso?' }).getByRole('button', { name: 'Eliminar' }).click()
    await expect(card).toHaveCount(0)
  })

  test('checklists: tick and untick an opening task', async ({ page }) => {
    await page.goto('/avisos?tab=checklists')
    const run = page.locator('[data-slot="card"]').filter({ hasText: 'Apertura del local' })
    const task = run.getByRole('button', { name: /Calibrar molienda del día/ })
    await expect(task).toBeVisible()
    const was = (await task.getAttribute('aria-pressed')) === 'true'

    await task.click()
    await expect(task).toHaveAttribute('aria-pressed', String(!was))
    if (!was) await expect(task).toContainText('Admin')

    await task.click() // restore
    await expect(task).toHaveAttribute('aria-pressed', String(was))
  })
})
