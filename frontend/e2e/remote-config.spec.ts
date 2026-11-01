import { expect, test } from './fixtures'

/**
 * Vendor remote config (announcements, support, minimum version) and subscription price changes.
 * The e2e stack has no license server: the API boundary is simulated with page.route.
 */
const CONFIG = {
  announcements: [
    { id: 41, title: 'Mantenimiento el domingo', body: 'El servidor de licencias se reinicia a las 3 AM.', level: 'warning' },
    { id: 42, title: 'Nueva guía de bebidas', body: '', level: 'info' },
  ],
  support: {
    email: 'soporte@example.com',
    whatsapp: '+54 9 11 0000-0000',
    terms_url: 'https://example.com/terminos',
    privacy_url: null,
  },
  min_version: null,
  required: false,
  release_notes_url: null,
}

test('announcements show in the app shell and stay closed once dismissed', async ({ page }) => {
  await page.route('**/api/remote-config', (route) => route.fulfill({ json: CONFIG }))
  await page.goto('/')
  const banner = page.getByTestId('announcements')
  await expect(banner).toContainText('Mantenimiento el domingo')
  await expect(banner).toContainText('Nueva guía de bebidas')
  await page.getByRole('button', { name: 'Cerrar aviso: Mantenimiento el domingo' }).click()
  await expect(banner).not.toContainText('Mantenimiento el domingo')
  await page.reload()
  await expect(page.getByTestId('announcements')).toContainText('Nueva guía de bebidas')
  await expect(page.getByText('Mantenimiento el domingo')).toHaveCount(0)
  await page.evaluate(() => localStorage.removeItem('bloom.dismissedAnnouncements'))
})

test('support contacts and legal links in Acerca de', async ({ page }) => {
  await page.route('**/api/remote-config', (route) => route.fulfill({ json: CONFIG }))
  await page.goto('/config?tab=acerca')
  const card = page.getByTestId('support-card')
  await expect(card.getByRole('link', { name: 'soporte@example.com' })).toHaveAttribute('href', 'mailto:soporte@example.com')
  await expect(card.getByRole('link', { name: /WhatsApp/ })).toHaveAttribute('href', 'https://wa.me/5491100000000')
  await expect(card.getByRole('link', { name: 'Términos y condiciones' })).toBeVisible()
  await expect(card.getByText('Política de privacidad')).toHaveCount(0)
})

test('an unsupported version shows "Actualización obligatoria"', async ({ page }) => {
  await page.route('**/api/updates', async (route) => {
    const res = await route.fetch()
    await route.fulfill({ response: res, json: { ...(await res.json()), min_version: '999.0.0', required: true } })
  })
  await page.goto('/config?tab=acerca')
  await expect(page.getByTestId('update-required')).toContainText('Actualización obligatoria')
  await expect(page.getByRole('link', { name: /Actualización obligatoria/ })).toBeVisible()
})

test('a subscriber accepts the new price from Configuración → Licencia', async ({ page }) => {
  let accepted = false
  const change = () => ({
    old_amount_cents: 1_000_000,
    new_amount_cents: 1_250_000,
    effective_at: '2026-12-15T03:00:00',
    accepted,
    needs_acceptance: true,
  })
  const subscription = () => ({
    has_subscription: true, status: 'authorized', plan: 'pro_mensual', plan_label: 'Pro mensual',
    amount_cents: 1_000_000, days: 30, paid_through: '2026-12-01T15:00:00', cancellation_code: null,
    pending_price_change: change(),
  })
  await page.route('**/api/license', async (route) => {
    const res = await route.fetch()
    await route.fulfill({
      response: res,
      json: {
        ...(await res.json()), server_configured: true, perpetual: false, expires_at: 1_800_000_000,
        pending_price_change: change(),
      },
    })
  })
  await page.route('**/api/license/plans', (route) => route.fulfill({ json: { currency: 'ARS', enabled: true, plans: {} } }))
  await page.route('**/api/license/subscription', (route) => route.fulfill({ json: subscription() }))
  await page.route('**/api/license/subscription/accept-price', (route) => {
    accepted = true
    return route.fulfill({ json: subscription() })
  })

  await page.goto('/')
  await expect(page.getByTestId('price-change-banner')).toContainText('15/12/2026')
  await page.getByTestId('price-change-banner').getByRole('link', { name: 'Revisar' }).click()

  const notice = page.getByTestId('price-change')
  await expect(notice).toContainText('Cambia el precio de tu suscripción')
  await expect(notice).toContainText('$ 12.500')
  await expect(notice.getByRole('button', { name: 'Cancelar suscripción' })).toBeVisible()
  await notice.getByRole('button', { name: 'Aceptar nuevo precio' }).click()
  await expect(page.getByRole('alertdialog')).toContainText('Podés cancelar la suscripción cuando quieras')
  await page.getByRole('button', { name: 'Aceptar', exact: true }).click()
  await expect(page.getByTestId('price-change')).toContainText('Aceptaste el nuevo precio')
  await expect(page.getByTestId('price-change-banner')).toHaveCount(0)
  // The "botón de baja" is still there after accepting
  await expect(page.getByRole('button', { name: 'Cancelar suscripción' })).toBeVisible()
})
