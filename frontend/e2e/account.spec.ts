import type { Page, Route } from '@playwright/test'

import { expect, test } from './fixtures'

/** The e2e backend has no license server: the /api/account endpoints are mocked per test. */
function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
}

const PREFS = {
  available: true,
  email: 'dueno@example.com',
  business_name: 'Café Demo',
  preferences: { news: false, updates: true, transactional: true },
  categories: [
    { key: 'news', label: 'Novedades y promociones', description: 'Ofertas y noticias.', locked: false },
    { key: 'updates', label: 'Actualizaciones del producto', description: 'Versiones nuevas.', locked: false },
    { key: 'transactional', label: 'Cobros, cambios de precio y seguridad', description: 'Obligatorios.', locked: true },
  ],
}

async function mockPrefs(page: Page, initial: unknown) {
  const puts: unknown[] = []
  let current = initial as typeof PREFS
  await page.route('**/api/account/preferences', async (route) => {
    if (route.request().method() === 'PUT') {
      const body = route.request().postDataJSON() as Record<string, boolean>
      puts.push(body)
      current = { ...current, preferences: { ...current.preferences, ...body } }
    }
    return json(route, current)
  })
  return puts
}

test('Notificaciones: switches load live from the server and save; transactional is locked', async ({ page }) => {
  const puts = await mockPrefs(page, PREFS)
  await page.goto('/config?tab=notificaciones')
  await expect(page.getByText('dueno@example.com')).toBeVisible()
  const news = page.getByRole('switch', { name: 'Novedades y promociones' })
  const updates = page.getByRole('switch', { name: 'Actualizaciones del producto' })
  const locked = page.getByRole('switch', { name: 'Cobros, cambios de precio y seguridad' })
  await expect(news).not.toBeChecked()
  await expect(updates).toBeChecked()
  await expect(locked).toBeChecked()
  await expect(locked).toBeDisabled()
  await news.click()
  await expect(news).toBeChecked()
  await expect(page.getByText('Preferencias de mails guardadas.')).toBeVisible()
  expect(puts).toEqual([{ news: true }])
})

test('Notificaciones: offline or without server shows the switches disabled with a clear message', async ({ page }) => {
  await mockPrefs(page, { available: false, reason: 'No se pudo conectar con el servidor de licencias.' })
  await page.goto('/config?tab=notificaciones')
  await expect(page.getByTestId('prefs-unavailable')).toContainText('No se pudo conectar')
  for (const name of ['Novedades y promociones', 'Actualizaciones del producto']) {
    await expect(page.getByRole('switch', { name })).toBeDisabled()
  }
})

test('Notificaciones: real backend without license server answers "not available"', async ({ page }) => {
  await page.goto('/config?tab=notificaciones')
  await expect(page.getByTestId('prefs-unavailable')).toContainText('no tiene servidor')
})

test('Cuenta: link this installation with email → code, then unlink', async ({ page }) => {
  let linked = false
  const calls: { path: string; body: unknown }[] = []
  await page.route('**/api/account', async (route) => {
    if (route.request().method() === 'DELETE') linked = false
    return json(route, {
      linked,
      account: linked ? { email: 'dueno@example.com', business_name: 'Café Demo', name: null, linked_at: 1 } : null,
      server_configured: true,
    })
  })
  await page.route('**/api/account/link/*', async (route) => {
    const path = new URL(route.request().url()).pathname
    const body = route.request().postDataJSON() as { code?: string }
    calls.push({ path, body })
    if (path.endsWith('/start')) return json(route, { ok: true, message: 'ok', expires_in: 900 })
    if (body.code !== '123456') return json(route, { detail: 'El código es incorrecto o venció.' }, 400)
    linked = true
    return json(route, {
      linked: true,
      account: { email: 'dueno@example.com', business_name: 'Café Demo', name: null, linked_at: 1 },
      server_configured: true,
      trial_status: 'has_license',
      trial_started: false,
    })
  })

  await page.goto('/config?tab=cuenta')
  const send = page.getByRole('button', { name: 'Mandarme el código' })
  await page.getByLabel('Tu email').fill('Dueno@Example.com')
  await expect(send).toBeDisabled() // terms not accepted yet
  await page.getByLabel(/Acepto los términos/).click()
  await page.getByLabel(/novedades y promociones/).click()
  await send.click()
  await expect(page.getByText('Revisá tu mail')).toBeVisible()
  expect(calls[0].body).toMatchObject({ email: 'Dueno@Example.com', accept_terms: true, marketing_opt_in: true })

  await page.getByLabel('Código').fill('111111')
  await page.getByRole('button', { name: 'Vincular' }).click()
  await expect(page.getByRole('alert')).toContainText('incorrecto')
  await page.getByLabel('Código').fill('123456')
  await page.getByRole('button', { name: 'Vincular' }).click()
  await expect(page.getByText('Computadora vinculada a tu cuenta.')).toBeVisible()
  await expect(page.getByText('dueno@example.com')).toBeVisible()

  await page.getByRole('button', { name: 'Desvincular' }).click()
  await page.getByRole('alertdialog').getByRole('button', { name: 'Desvincular' }).click()
  await expect(page.getByRole('button', { name: 'Mandarme el código' })).toBeVisible()
})

test('Cuenta: without a license server the app explains no account is needed', async ({ page }) => {
  await page.goto('/config?tab=cuenta')
  await expect(page.getByTestId('account-unavailable')).toContainText('no hace falta una cuenta')
})
