import path from 'node:path'

import type { Page } from '@playwright/test'

import { expect, test } from './fixtures'
import { authHeaders, ensureCashOpenApi, money, pickDate, uid } from './helpers'

/** Optional screenshots for reviews: BLOOM_SHOTS=<folder>. */
async function shot(page: Page, name: string) {
  if (process.env.BLOOM_SHOTS) await page.screenshot({ path: path.join(process.env.BLOOM_SHOTS, `${name}.png`), fullPage: true })
}

async function pickCategory(page: Page, dialogName: string, category: string) {
  const dialog = page.getByRole('dialog', { name: dialogName })
  await dialog.getByLabel('Categoría').click()
  await page.getByRole('option', { name: category }).click()
}

test('expenses: cash expense out of the drawer, pending → paid, monthly fixed expense, real profit', async ({ page, request }) => {
  test.setTimeout(90_000)
  const headers = await authHeaders(page)
  await ensureCashOpenApi(page, request)
  const before = await (await request.get('/api/cash/current', { headers })).json()
  const tag = uid()

  await page.goto('/gastos')
  await expect(page.getByRole('heading', { level: 1, name: 'Gastos' })).toBeVisible()
  await expect(page.getByTestId('month-result')).toContainText('Ganancia real')

  // A variable expense paid with cash from the open drawer.
  await page.getByRole('button', { name: 'Nuevo gasto' }).click()
  await pickCategory(page, 'Nuevo gasto', 'Limpieza y descartables')
  const form = page.getByRole('dialog', { name: 'Nuevo gasto' })
  await form.getByLabel('Concepto').fill(`Lavandina ${tag}`)
  await form.getByLabel('Monto').fill('2500')
  await form.getByLabel('Medio de pago').click()
  await page.getByRole('option', { name: 'Efectivo' }).click()
  await form.getByRole('switch', { name: 'Sale de la caja' }).click()
  await form.getByRole('button', { name: 'Cargar gasto' }).click()
  await expect(form).toBeHidden()
  const row = page.getByRole('row').filter({ hasText: `Lavandina ${tag}` })
  await expect(row).toContainText('Pagado')
  await expect(row).toContainText('de la caja')
  await expect(row).toContainText(money(250_000))
  const after = await (await request.get('/api/cash/current', { headers })).json()
  expect(after.expected_cash_cents).toBe(before.expected_cash_cents - 250_000)
  expect(after.movements.some((m: { reason: string }) => m.reason === `Gasto: Lavandina ${tag}`)).toBe(true)

  // A pending one due tomorrow: shows in Avisos, then gets paid.
  await page.getByRole('button', { name: 'Nuevo gasto' }).click()
  await pickCategory(page, 'Nuevo gasto', 'Impuestos y tasas')
  await form.getByLabel('Concepto').fill(`ABL ${tag}`)
  await form.getByLabel('Monto').fill('18000')
  await form.getByRole('radio', { name: 'Pendiente de pago' }).click()
  const tomorrow = new Date(Date.now() + 86_400_000)
  const iso = `${tomorrow.getFullYear()}-${String(tomorrow.getMonth() + 1).padStart(2, '0')}-${String(tomorrow.getDate()).padStart(2, '0')}`
  await pickDate(form, 'Vence el', iso)
  await form.getByRole('button', { name: 'Cargar gasto' }).click()
  const pending = page.getByRole('row').filter({ hasText: `ABL ${tag}` })
  await expect(pending).toContainText('Pendiente')
  await shot(page, 'expenses-screen')

  await request.post('/api/alerts/refresh', { headers })
  await page.goto('/avisos')
  await expect(page.getByText(`Gasto vence en 1 día: ABL ${tag}`)).toBeVisible()

  await page.goto('/gastos')
  await pending.getByRole('button', { name: 'Pagar' }).click()
  const pay = page.getByRole('dialog', { name: 'Marcar como pagado' })
  await pay.getByLabel('Monto pagado').fill('18500')
  await pay.getByRole('button', { name: /Pagar/ }).click()
  await expect(pay).toBeHidden()
  await expect(pending).toContainText('Pagado')
  await expect(pending).toContainText(money(1_850_000))

  // Monthly fixed expense: generated as pending for this month.
  await page.getByRole('tab', { name: 'Fijos mensuales' }).click()
  await page.getByRole('button', { name: 'Nuevo gasto fijo' }).click()
  await pickCategory(page, 'Nuevo gasto fijo mensual', 'Abonos y suscripciones')
  const rec = page.getByRole('dialog', { name: 'Nuevo gasto fijo mensual' })
  await rec.getByLabel('Concepto').fill(`Alarma ${tag}`)
  await rec.getByLabel('Monto estimado').fill('9000')
  await rec.getByLabel('Vence el día').fill('28')
  await rec.getByRole('button', { name: 'Guardar' }).click()
  await expect(rec).toBeHidden()
  await expect(page.getByText(`Alarma ${tag}`)).toBeVisible()
  await page.getByRole('tab', { name: 'Gastos del mes' }).click()
  await expect(page.getByRole('row').filter({ hasText: `Alarma ${tag}` })).toContainText('Pendiente')

  // Dashboard card.
  await page.goto('/')
  await expect(page.getByTestId('profit-card')).toContainText('Ganancia real del mes')
  await expect(page.getByTestId('profit-card')).toContainText('Gastos')
})

test('expenses: delete removes the cash egreso while the drawer is open', async ({ page, request }) => {
  const headers = await authHeaders(page)
  await ensureCashOpenApi(page, request)
  const cats: { id: number; name: string }[] = await (await request.get('/api/expenses/categories', { headers })).json()
  const tag = uid()
  const res = await request.post('/api/expenses', {
    headers,
    data: { category_id: cats.find((c) => c.name === 'Otros')!.id, description: `Flete ${tag}`, amount_cents: 100_000, payment_method: 'efectivo', from_cash: true },
  })
  expect(res.ok(), await res.text()).toBeTruthy()
  const cash = (await (await request.get('/api/cash/current', { headers })).json()).expected_cash_cents
  await page.goto('/gastos')
  const row = page.getByRole('row').filter({ hasText: `Flete ${tag}` })
  await row.getByRole('button', { name: `Acciones de Flete ${tag}` }).click()
  await page.getByRole('menuitem', { name: 'Borrar' }).click()
  await page.getByRole('alertdialog').getByRole('button', { name: 'Borrar' }).click()
  await expect(row).toBeHidden()
  expect((await (await request.get('/api/cash/current', { headers })).json()).expected_cash_cents).toBe(cash + 100_000)
})
