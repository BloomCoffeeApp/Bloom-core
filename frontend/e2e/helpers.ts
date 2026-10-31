import type { APIRequestContext, Locator, Page } from '@playwright/test'

import { ADMIN } from './constants'
import { e2eProLicense } from './license'
import { enterPin, ensureCashOpen, expect } from './fixtures'

/** Same formatter as `fmtMoney` in src/lib/format.ts ("$ 1.234,56", with the es-AR NBSP). */
const MONEY = new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', minimumFractionDigits: 2 })
const MONEY_SHORT = new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', maximumFractionDigits: 0 })
export const money = (cents: number) => MONEY.format(cents / 100)
export const moneyShort = (cents: number) => MONEY_SHORT.format(cents / 100)

/** Short unique suffix so specs never collide on names in the shared DB. */
export const uid = () => `${Date.now().toString(36)}${Math.floor(Math.random() * 1e3)}`

/** Bearer header of the session stored in the browser context (the saved admin session). */
export async function authHeaders(page: Page) {
  const state = await page.context().storageState()
  const token = state.origins.flatMap((o) => o.localStorage).find((e) => e.name === 'cafe.token')?.value
  expect(token, 'no saved session in this browser context').toBeTruthy()
  return { Authorization: `Bearer ${token}` }
}

/** Removes the Pro license for the duration of `fn` (Free plan), ALWAYS restoring it afterwards. */
export async function withFreePlan(page: Page, request: APIRequestContext, fn: () => Promise<void>) {
  const headers = await authHeaders(page)
  try {
    const res = await request.delete('/api/license', { headers })
    expect(res.ok(), await res.text()).toBeTruthy()
    await fn()
  } finally {
    const res = await request.post('/api/license/import', { data: { token: e2eProLicense() }, headers })
    expect(res.ok(), await res.text()).toBeTruthy()
  }
}

/** Opens a cash session through the API when none is open (setup shortcut for non-cash specs). */
export async function ensureCashOpenApi(page: Page, request: APIRequestContext) {
  const headers = await authHeaders(page)
  const cur = await request.get('/api/cash/current', { headers })
  if ((await cur.text()) === 'null') {
    const res = await request.post('/api/cash/open', { data: { opening_cents: 1_000_000 }, headers })
    expect(res.ok(), await res.text()).toBeTruthy()
  }
}

/** Goes to the POS with the cash open and an empty cart. */
export async function openPos(page: Page) {
  await page.goto('/pos')
  await ensureCashOpen(page)
  const empty = page.getByRole('button', { name: 'Vaciar' })
  if (await empty.isVisible()) await empty.click()
}

/** POS product tile by exact product name. */
export const productTile = (page: Page, name: string) =>
  page.getByRole('button', { name: new RegExp(`^${escapeRe(name)}\\s*\\$`) }).first()

/** The cart line `<li>` of a product. */
export const cartLine = (page: Page, name: string) =>
  page.locator('li').filter({ has: page.getByText(name, { exact: true }) })

/** In the POS: associates an existing customer through the picker. */
export async function pickCustomer(page: Page, name: string) {
  await page.getByRole('button', { name: 'Cliente (opcional)' }).click()
  const dialog = page.getByRole('dialog', { name: 'Elegir cliente' })
  await dialog.getByPlaceholder('Nombre o teléfono…').fill(name)
  await dialog.getByRole('button', { name: new RegExp(escapeRe(name)) }).click()
  await expect(dialog).toBeHidden()
  await expect(page.getByRole('button', { name: 'Quitar cliente' })).toBeVisible()
}

export async function openCheckout(page: Page) {
  await page.getByRole('button', { name: /COBRAR/ }).click()
  const dialog = page.getByRole('dialog', { name: 'Cobrar' })
  await expect(dialog.getByText('Total a cobrar')).toBeVisible()
  return dialog
}

/** Confirms the open checkout dialog and returns the success dialog. */
export async function confirmCheckout(page: Page, dialog: Locator) {
  await dialog.getByRole('button', { name: /Confirmar cobro/ }).click()
  const done = page.getByRole('dialog').filter({ hasText: '¡Venta cobrada!' })
  await expect(done).toBeVisible()
  return done
}

/** Ticket number shown in the success dialog. */
export async function ticketNumber(done: Locator) {
  const text = await done.getByText(/Ticket #\d+/).innerText()
  return Number(/#(\d+)/.exec(text)![1])
}

/** Creates a customer through the API and returns it. */
export async function createCustomerApi(page: Page, request: APIRequestContext, data: Record<string, unknown>) {
  const res = await request.post('/api/customers', { data, headers: await authHeaders(page) })
  expect(res.ok(), await res.text()).toBeTruthy()
  return (await res.json()) as { id: number; name: string }
}

/** Fresh browser login through the PIN pad, with the guided tour pre-dismissed. */
export async function freshLogin(page: Page, name = ADMIN.name, pin = ADMIN.pin) {
  await page.addInitScript(() => {
    for (let i = 1; i <= 100; i++) localStorage.setItem(`bloom.tour.done.${i}`, '1')
  })
  await page.goto('/')
  await page.getByRole('button', { name: new RegExp(name) }).click()
  await enterPin(page, pin)
  await expect(page.getByRole('button', { name: 'Bloquear' })).toBeVisible()
}

export const escapeRe = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

/** A StatCard (label + value + hint), located by its exact label. */
export const statCard = (scope: Page | Locator, label: string) =>
  scope.getByText(label, { exact: true }).first().locator('xpath=ancestor::*[@data-slot="card"][1]')
