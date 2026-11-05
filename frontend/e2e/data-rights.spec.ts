import type { Route } from '@playwright/test'

import { expect, test } from './fixtures'

/** Configuración → Cuenta → Tus datos (server mocked) and Acerca de → Licencias de terceros. */
function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
}

const LINKED = {
  linked: true,
  account: { email: 'dueno@example.com', business_name: 'Café Demo', name: null, linked_at: 1 },
  server_configured: true,
}

test('Tus datos: without a server explains the business data stays in this computer', async ({ page }) => {
  await page.goto('/config?tab=cuenta')
  await expect(page.getByTestId('local-data-note')).toContainText('solo en esta computadora')
  await expect(page.getByText('no guardamos ningún dato tuyo')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Eliminar mi cuenta' })).toHaveCount(0)
})

test('Tus datos: download the account data and delete the account with an email code', async ({ page }) => {
  let linked = true
  const codes: string[] = []
  await page.route('**/api/account', (route) => json(route, linked ? LINKED : { ...LINKED, linked: false, account: null }))
  await page.route('**/api/account/data/export', (route) =>
    json(route, { customer: { email: 'dueno@example.com' }, licenses: [], retention: {} }),
  )
  await page.route('**/api/account/delete/start', (route) => json(route, { ok: true, email: 'du…@example.com', expires_in: 900 }))
  await page.route('**/api/account/delete/confirm', (route) => {
    const { code } = route.request().postDataJSON() as { code: string }
    codes.push(code)
    if (code !== '123456') return json(route, { detail: 'El código es incorrecto o venció.' }, 400)
    linked = false
    return json(route, { ...LINKED, linked: false, account: null, deleted: true, retained: ['Los cobros quedan anonimizados.'] })
  })

  await page.goto('/config?tab=cuenta')
  const download = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Descargar mis datos de la cuenta' }).click()
  expect((await download).suggestedFilename()).toMatch(/^bloom-mis-datos-.*\.json$/)

  await page.getByRole('button', { name: 'Eliminar mi cuenta' }).click()
  const dialog = page.getByRole('alertdialog')
  await expect(dialog).toContainText('cancelala primero')
  await dialog.getByRole('button', { name: 'Enviarme el código' }).click()
  const code = page.getByLabel(/Código que te mandamos a du…@example.com/)
  const erase = page.getByRole('button', { name: 'Eliminar definitivamente' })
  await expect(erase).toBeDisabled()
  await code.fill('111111')
  await erase.click()
  await expect(page.getByText('El código es incorrecto o venció.').first()).toBeVisible()
  await code.fill('123456')
  await erase.click()
  await expect(page.getByTestId('account-deleted')).toContainText('anonimizados')
  expect(codes).toEqual(['111111', '123456'])
})

test('Acerca de: third-party licenses are searchable and show the full text', async ({ page }) => {
  await page.route('**/api/system/third-party-licenses', (route) =>
    json(route, {
      available: true,
      generated_at: '2026-11-05T00:00:00+00:00',
      packages: [
        { name: '@fontsource-variable/inter', version: '5.3.0', license: 'OFL-1.1', source: 'frontend', homepage: '',
          copyright: ['Copyright 2016 The Inter Project Authors'], text: 'SIL OPEN FONT LICENSE Version 1.1', note: '' },
        { name: 'fastapi', version: '0.162.0', license: 'MIT', source: 'backend', homepage: 'https://fastapi.tiangolo.com',
          copyright: [], text: 'The MIT License (MIT)', note: '' },
        { name: 'lucide-react', version: '1.65.0', license: 'ISC', source: 'frontend', homepage: '',
          copyright: ['Copyright (c) Lucide Icons and Contributors'], text: 'ISC License', note: '' },
      ],
    }),
  )
  await page.goto('/config?tab=acerca')
  await page.getByRole('button', { name: 'Ver licencias' }).click()
  const dialog = page.getByRole('dialog', { name: 'Licencias de terceros' })
  await expect(dialog.getByText('3 de 3 componentes')).toBeVisible()
  await dialog.getByLabel('Buscar licencias').fill('isc')
  await expect(dialog.getByText('1 de 3 componentes')).toBeVisible()
  await expect(dialog.getByTestId('third-party-current')).toContainText('lucide-react')
  await expect(dialog.locator('pre')).toContainText('ISC License')
  await dialog.getByLabel('Buscar licencias').fill('')
  await dialog.getByRole('button', { name: /fontsource-variable\/inter/ }).click()
  await expect(dialog.locator('pre')).toContainText('SIL OPEN FONT LICENSE')
})

test('Acerca de: real backend answers the licenses endpoint', async ({ page }) => {
  await page.goto('/config?tab=acerca')
  await page.getByRole('button', { name: 'Ver licencias' }).click()
  const dialog = page.getByRole('dialog', { name: 'Licencias de terceros' })
  // From source the list exists only after build/third_party_notices.py ran; both states are valid.
  await expect(dialog.getByText(/componentes|Lista no disponible/).first()).toBeVisible()
})
