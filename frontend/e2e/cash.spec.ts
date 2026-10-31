import type { APIRequestContext, Page } from '@playwright/test'

import { expect, test } from './fixtures'
import { authHeaders, money, statCard } from './helpers'

/** Closes whatever session is open (counting exactly the expected amounts) so the spec starts from "closed". */
async function closeOpenSession(page: Page, request: APIRequestContext) {
  const headers = await authHeaders(page)
  const cur = await (await request.get('/api/cash/current', { headers })).json()
  if (!cur) return
  const counts = cur.by_method.map((m: { method: string; expected_cents: number }) => ({
    payment_method: m.method,
    counted_cents: m.expected_cents,
  }))
  const res = await request.post('/api/cash/close', { data: { counts }, headers })
  expect(res.ok(), await res.text()).toBeTruthy()
}

test('open the cash, add an income and an expense, close with the count and see the Z report', async ({ page, request, errors }) => {
  await page.goto('/caja')
  await closeOpenSession(page, request)
  await page.reload()
  await expect(page.getByText('La caja está cerrada')).toBeVisible()

  // Open with $15.000
  await page.getByRole('button', { name: 'Abrir caja' }).first().click()
  const open = page.getByRole('dialog', { name: /Abrir caja/ })
  await open.getByLabel('Fondo inicial en efectivo').fill('15000')
  await open.getByRole('button', { name: 'Abrir caja' }).click()
  await expect(open).toBeHidden()
  await expect(statCard(page, 'Fondo inicial')).toContainText(money(1_500_000))

  // Income $2.000
  await page.getByRole('button', { name: 'Ingreso', exact: true }).click()
  const inDlg = page.getByRole('dialog', { name: /Ingreso de efectivo/ })
  await inDlg.getByLabel('Monto').fill('2000')
  await inDlg.getByLabel('Motivo').fill('Cambio e2e')
  await inDlg.getByRole('button', { name: 'Registrar' }).click()
  await expect(inDlg).toBeHidden()
  await expect(page.getByText('Cambio e2e')).toBeVisible()

  // Expense $500 (suggestion chip + edit)
  await page.getByRole('button', { name: 'Egreso', exact: true }).click()
  const outDlg = page.getByRole('dialog', { name: /Egreso de efectivo/ })
  await outDlg.getByLabel('Monto').fill('500')
  await outDlg.getByRole('button', { name: 'Pago a proveedor' }).click()
  await expect(outDlg.getByLabel('Motivo')).toHaveValue('Pago a proveedor')
  await outDlg.getByRole('button', { name: 'Registrar' }).click()
  await expect(outDlg).toBeHidden()

  await expect(page.getByText(`Ingresos ${money(200_000)}`)).toBeVisible()
  await expect(page.getByText(`Egresos ${money(50_000)}`)).toBeVisible()
  // 15.000 + 2.000 − 500
  await expect(statCard(page, 'Efectivo esperado')).toContainText(money(1_650_000))

  // Close counting $16.400 of cash → −$100
  await page.getByRole('button', { name: 'Cerrar caja' }).click()
  const close = page.getByRole('dialog', { name: /Cerrar caja · arqueo/ })
  const confirm = close.getByRole('button', { name: 'Cerrar caja' })
  await expect(confirm).toBeDisabled() // cash not counted yet
  await close.getByLabel('Contado Efectivo').fill('16400')
  const total = close.getByText('Diferencia total').locator('..')
  await expect(total).toContainText(money(-10_000))
  await close.getByLabel('Observaciones').fill('Arqueo e2e')
  await confirm.click()
  await expect(close).toBeHidden()

  // Z report sheet
  const z = page.getByRole('dialog', { name: /Cierre de caja #\d+/ })
  await expect(z.getByText('Cerrada', { exact: true })).toBeVisible()
  await expect(z.getByText('Fondo inicial').locator('..')).toContainText(money(1_500_000))
  await expect(z.getByText('Diferencia total').locator('..')).toContainText(money(-10_000))
  const title = await z.getByRole('heading', { name: /Cierre de caja #\d+/ }).innerText()
  const id = /#(\d+)/.exec(title)![1]
  await page.keyboard.press('Escape')
  await expect(z).toBeHidden()
  await expect(page.getByText('La caja está cerrada')).toBeVisible()

  // History
  await page.getByRole('tab', { name: /Historial de cierres/ }).click()
  const row = page.getByRole('row').filter({ hasText: `#${id}` })
  await expect(row).toContainText(money(-10_000))
  await row.click()
  await expect(page.getByRole('dialog', { name: `Cierre de caja #${id}` })).toBeVisible()
  expect(errors.consoleErrors).toEqual([])
})
