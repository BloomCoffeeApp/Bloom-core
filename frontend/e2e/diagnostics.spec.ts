import type { Page, Route } from '@playwright/test'

import { expect, test } from './fixtures'

/** Configuración → Acerca de → «Enviar diagnóstico a soporte». The e2e backend has no license server:
 *  the real endpoint answers "not available" (first test); the rest mock /api/diagnostics. */
function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
}

const PREVIEW = {
  available: true,
  reason: null,
  includes_license: true,
  diagnostic: {
    os: 'Windows-11-10.0.26200-SP0',
    app_version: '1.2.3',
    db_ok: true,
    db_size_mb: 4.5,
    last_backup_at: '2026-11-13T03:00:00Z',
    backups: 7,
    printer: { configured: true, last_ok: false },
    license: { state: 'active', plan: 'pro', expires: null },
    modules: ['orders', 'stock'],
    errors: [{ ts: '2026-11-13 10:00:00', kind: 'cafeteria.printing', message: 'No se pudo imprimir en [usuario]' }],
    uptime_hours: 5.5,
  },
}

async function mockPreview(page: Page, preview: unknown = PREVIEW) {
  await page.route('**/api/diagnostics/preview', (route) => json(route, preview))
}

async function openDialog(page: Page) {
  await page.goto('/config?tab=acerca')
  await page.getByRole('button', { name: 'Enviar diagnóstico a soporte' }).click()
  return page.getByRole('dialog', { name: 'Enviar diagnóstico a soporte' })
}

test('without a support server the dialog explains it and cannot send', async ({ page }) => {
  const dialog = await openDialog(page) // real backend: no license server configured
  await expect(dialog.getByTestId('diagnostic-unavailable')).toContainText('servidor')
  await expect(dialog.getByRole('button', { name: 'Enviar', exact: true })).toHaveCount(0)
})

test('shows exactly what is sent, needs consent, then shows the support code and copies it', async ({ page, context }) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write'])
  await mockPreview(page)
  const bodies: unknown[] = []
  await page.route('**/api/diagnostics/send', (route) => {
    bodies.push(route.request().postDataJSON())
    return json(route, { support_code: 'BLM-ABCD-2345' })
  })
  const dialog = await openDialog(page)
  const summary = dialog.getByTestId('diagnostic-summary')
  await expect(summary).toContainText('1.2.3')
  await expect(summary).toContainText('En buen estado')
  await expect(summary).toContainText('la última impresión falló')
  await expect(dialog.getByTestId('diagnostic-errors')).toContainText('cafeteria.printing')
  await expect(dialog).not.toContainText('@')

  const send = dialog.getByRole('button', { name: 'Enviar', exact: true })
  const consent = dialog.getByRole('checkbox')
  await expect(consent).not.toBeChecked()
  await expect(send).toBeDisabled()
  expect(Math.round((await send.boundingBox())?.height ?? 0)).toBeGreaterThanOrEqual(44) // sub-pixel rounding
  await consent.click()
  await send.click()

  await expect(dialog.getByTestId('support-code')).toHaveText('BLM-ABCD-2345')
  expect(bodies).toEqual([{ consent: true }])
  await dialog.getByRole('button', { name: 'Copiar' }).click()
  await expect(dialog.getByRole('button', { name: 'Copiado' })).toBeVisible()
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe('BLM-ABCD-2345')
})

test('send errors are clear: no internet and rate limit', async ({ page }) => {
  await mockPreview(page)
  let status = 503
  await page.route('**/api/diagnostics/send', (route) =>
    json(route, { detail: status === 503 ? 'No se pudo conectar con el servidor de licencias.' : 'Ya mandaste varios.' }, status),
  )
  const dialog = await openDialog(page)
  await dialog.getByRole('checkbox').click()
  await dialog.getByRole('button', { name: 'Enviar', exact: true }).click()
  await expect(dialog.getByTestId('diagnostic-error')).toContainText('Revisá tu conexión a internet')
  status = 429
  await dialog.getByRole('button', { name: 'Enviar', exact: true }).click()
  await expect(dialog.getByTestId('diagnostic-error')).toContainText('Ya mandaste varios diagnósticos')
  await expect(dialog.getByRole('button', { name: 'Enviar', exact: true })).toBeEnabled() // can retry later
})
