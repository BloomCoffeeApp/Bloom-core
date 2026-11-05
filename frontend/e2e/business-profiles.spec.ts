import path from 'node:path'

import type { APIRequestContext, Page } from '@playwright/test'

import { ADMIN } from './constants'
import { expect, test } from './fixtures'
import { authHeaders } from './helpers'

/** Optional: SHOTS_DIR=<folder> saves review screenshots of the new screens. */
const SHOTS = process.env.SHOTS_DIR

async function shot(page: Page, name: string) {
  if (!SHOTS) return
  for (const scheme of ['light', 'dark'] as const) {
    await page.emulateMedia({ colorScheme: scheme })
    await page.waitForTimeout(300)
    await page.screenshot({ path: path.join(SHOTS, `${name}-${scheme}.png`) })
  }
  await page.emulateMedia({ colorScheme: 'light' })
}

const nav = (page: Page) => page.locator('[data-slot="sidebar"]').first()

async function setProfile(request: APIRequestContext, headers: Record<string, string>, profile: string) {
  const res = await request.put('/api/business/profile', { data: { profile, modules: {} }, headers })
  expect(res.ok(), await res.text()).toBeTruthy()
}

test.describe('setup wizard', () => {
  test.use({ storageState: { cookies: [], origins: [] } })

  test('choosing "Cafetería chica" in the wizard simplifies the nav', async ({ page, request }) => {
    // The shared e2e DB is already set up: the wizard is shown by faking the setup status, and the
    // final POST is checked and then applied to the real backend (pytest covers POST /api/setup itself).
    const users: { id: number; name: string }[] = await (await request.get('/api/auth/users')).json()
    const admin = users.find((u) => u.name === ADMIN.name)!
    const loginRes = await request.post('/api/auth/login', { data: { user_id: admin.id, pin: ADMIN.pin } })
    const login = await loginRes.json()
    const headers = { Authorization: `Bearer ${login.token}` }
    await page.addInitScript((id) => localStorage.setItem(`bloom.tour.done.${id}`, '1'), admin.id)

    let sent: { profile?: string; modules?: Record<string, boolean>; business_name?: string } | null = null
    await page.route('**/api/setup/status', (route) =>
      route.fulfill({ json: { needs_setup: sent === null, business: { name: '' } } }),
    )
    await page.route('**/api/setup', async (route) => {
      sent = route.request().postDataJSON()
      await setProfile(request, headers, sent!.profile!)
      await route.fulfill({ json: login })
    })

    try {
      await page.goto('/')
      await page.getByLabel('Nombre de la cafetería').fill('Café Wizard')
      await page.getByLabel('Tu nombre (administrador)').fill('Admin')
      await page.getByLabel('PIN (4 a 6 números)').fill('0000')
      await page.getByLabel('Repetir PIN').fill('0000')
      await page.getByRole('button', { name: 'Siguiente' }).click()

      await expect(page.getByText('¿Qué tipo de negocio tenés?')).toBeVisible()
      await expect(page.getByRole('button', { name: 'Empezar' })).toBeDisabled()
      await page.getByTestId('profile-small').click()
      await shot(page, 'wizard-step')
      await page.getByRole('button', { name: 'Personalizar módulos' }).click()
      // Small café: no order screen by default; tables need dine-in (on) but are off.
      await expect(page.getByRole('switch', { name: 'Pantalla de pedidos' })).not.toBeChecked()
      await expect(page.getByRole('switch', { name: 'Estaciones y pantalla de retiro' })).toBeDisabled()
      await page.getByRole('switch', { name: 'Promos' }).click() // owner turns promos back on
      await shot(page, 'wizard-customize')
      await page.getByRole('button', { name: 'Empezar' }).click()

      await expect(page.getByRole('heading', { level: 1 })).toContainText(ADMIN.name)
      expect(sent).toMatchObject({ business_name: 'Café Wizard', profile: 'small', modules: { promos: true } })
      const sidebar = nav(page)
      await expect(sidebar.getByRole('link', { name: 'Punto de venta' })).toBeVisible()
      await expect(sidebar.getByRole('link', { name: 'Productos' })).toBeVisible()
      await expect(sidebar.getByRole('link', { name: 'Pedidos' })).toHaveCount(0)
      await expect(sidebar.getByRole('link', { name: 'Compras' })).toHaveCount(0)
      await expect(page.getByTestId('orders-strip')).toHaveCount(0)
      await shot(page, 'nav-simplified')
    } finally {
      await setProfile(request, headers, 'salon')
    }
  })
})

test('switching the business type shows a preview and hides/shows sections', async ({ page, request }) => {
  const headers = await authHeaders(page)
  try {
    await page.goto('/config?tab=negocio')
    const card = page.getByTestId('current-profile')
    await expect(card).toContainText('Cafetería con salón')
    await expect(nav(page).getByRole('link', { name: 'Barista' })).toBeVisible()
    await page.getByRole('button', { name: 'Cambiar tipo de negocio' }).scrollIntoViewIfNeeded()
    await shot(page, 'settings-profile')

    await page.getByRole('button', { name: 'Cambiar tipo de negocio' }).click()
    const dialog = page.getByRole('dialog', { name: 'Cambiar tipo de negocio' })
    await expect(dialog.getByRole('button', { name: 'Guardar cambios' })).toBeDisabled() // nothing changed yet
    await dialog.getByTestId('profile-delivery').click()
    const preview = dialog.getByTestId('profile-preview')
    await expect(preview).toContainText('Se van a ocultar')
    for (const label of ['Consumo en el local', 'Mesas', 'Barista', 'Fidelización', 'Menú para clientes'])
      await expect(preview.getByText(label, { exact: true })).toBeVisible()
    await expect(preview).toContainText('Nada nuevo.')
    await shot(page, 'settings-profile-change')
    await dialog.getByRole('button', { name: 'Guardar cambios' }).click()
    await expect(dialog).toBeHidden()

    await expect(card).toContainText('Solo pedidos / delivery')
    const sidebar = nav(page)
    await expect(sidebar.getByRole('link', { name: 'Barista' })).toHaveCount(0)
    await expect(sidebar.getByRole('link', { name: 'Pedidos' })).toBeVisible()
    await expect(page.getByRole('tab', { name: 'Fidelización' })).toHaveCount(0)
    await expect(page.getByRole('tab', { name: 'Mesas y pedidos QR' })).toHaveCount(0)

    // POS: only "Para llevar" and "Delivery", no table number.
    await page.goto('/pos')
    await expect(page.getByRole('button', { name: 'Para llevar' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Delivery' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Salón' })).toHaveCount(0)
    await expect(page.getByLabel('Mesa', { exact: true })).toHaveCount(0)

    // Back to "con salón" from the same dialog: everything comes back.
    await page.goto('/config?tab=negocio')
    await page.getByRole('button', { name: 'Cambiar tipo de negocio' }).click()
    await dialog.getByTestId('profile-salon').click()
    await expect(dialog.getByTestId('profile-preview')).toContainText('Nada se oculta.')
    await dialog.getByRole('button', { name: 'Guardar cambios' }).click()
    await expect(sidebar.getByRole('link', { name: 'Barista' })).toBeVisible()
    await expect(page.getByRole('tab', { name: 'Fidelización' })).toBeVisible()
  } finally {
    await setProfile(request, headers, 'salon')
  }
})

test('a hidden module deep link shows a friendly page that turns it back on', async ({ page, request }) => {
  const headers = await authHeaders(page)
  try {
    await setProfile(request, headers, 'small') // no order screen
    await page.goto('/pedidos')
    const hidden = page.getByTestId('hidden-module')
    await expect(hidden).toContainText('Este módulo está oculto para tu tipo de negocio')
    await expect(hidden).toContainText('Pantalla de pedidos')
    await expect(nav(page).getByRole('link', { name: 'Pedidos' })).toHaveCount(0)
    await shot(page, 'hidden-module')
    await hidden.getByRole('button', { name: 'Activarlo' }).click()
    await expect(hidden).toBeHidden()
    await expect(nav(page).getByRole('link', { name: 'Pedidos' })).toBeVisible()
    const info = await (await request.get('/api/business/modules', { headers })).json()
    expect(info).toMatchObject({ profile: 'small', overrides: { orders: true } })
  } finally {
    await setProfile(request, headers, 'salon')
  }
})

test('the subscribe card shows the plan recommended for the business type first', async ({ page, request }) => {
  const headers = await authHeaders(page)
  // No license server in the e2e stack: a trial license and the server's plans at the API boundary.
  await page.route('**/api/license', async (route) => {
    const res = await route.fetch()
    await route.fulfill({ response: res, json: { ...(await res.json()), server_configured: true, plan: 'trial' } })
  })
  const plan = (label: string, profiles?: string[]) => ({
    label, description: '', amount_cents: 1_000_000, frequency: 1, frequency_type: 'months', devices: 1, profiles,
  })
  await page.route('**/api/license/plans', (route) =>
    route.fulfill({
      json: {
        currency: 'ARS', enabled: true,
        plans: { a: plan('Plan A', ['salon']), b: plan('Plan B'), c: plan('Plan Mostrador', ['takeaway', 'small']) },
      },
    }),
  )
  try {
    await setProfile(request, headers, 'takeaway')
    await page.goto('/config?tab=licencia')
    const plans = page.getByRole('radiogroup', { name: 'Plan' }).getByRole('radio')
    await expect(plans).toHaveCount(3)
    await expect(plans.first()).toContainText('Plan Mostrador')
    await expect(plans.first()).toContainText('Recomendado para take away / al paso')
    await expect(plans.first()).toHaveAttribute('aria-checked', 'true')
    await expect(page.getByTestId('plan-recommended')).toHaveCount(1)
  } finally {
    await setProfile(request, headers, 'salon')
  }
})
