import { type BrowserContext, expect, type Page, test } from '@playwright/test'

const OWNER = { name: 'Dueño Demo', pin: '1234' }

async function openDemo(context: BrowserContext): Promise<Page> {
  // The guided tour opens on a user's first login; keep it out of the way.
  await context.addInitScript(() => {
    for (let i = 1; i <= 20; i++) localStorage.setItem(`bloom.tour.done.${i}`, '1')
  })
  const page = await context.newPage()
  // The template is built a few seconds after startup: the waiting page reloads itself.
  await expect(async () => {
    // Production serves the page from the demo server, which creates the sandbox; behind the Vite
    // dev server the "Empezar la demo" link does it (same as after an idle sandbox was deleted).
    await page.goto('/')
    const start = page.getByRole('link', { name: 'Empezar la demo' })
    const owner = page.getByRole('button', { name: new RegExp(OWNER.name) })
    await expect(start.or(owner).first()).toBeVisible({ timeout: 5_000 })
    if (await start.isVisible()) await start.click()
    await expect(owner).toBeVisible({ timeout: 5_000 })
  }).toPass({ timeout: 45_000 })
  return page
}

async function login(page: Page) {
  await page.getByRole('button', { name: new RegExp(OWNER.name) }).click()
  for (const d of OWNER.pin) await page.getByRole('button', { name: d, exact: true }).click()
  await page.getByRole('button', { name: 'Entrar' }).click()
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Dueño')
}

async function sellMedialuna(page: Page) {
  await page.goto('/pos')
  const closed = page.getByText('La caja está cerrada')
  await expect(closed.or(page.getByRole('button', { name: /COBRAR/ })).first()).toBeVisible()
  await page.waitForLoadState('networkidle')
  if (await closed.isVisible()) {
    await page.getByRole('button', { name: 'Abrir caja' }).click()
    const dialog = page.getByRole('dialog', { name: /Abrir caja/ })
    await dialog.getByRole('button', { name: /\$/ }).first().click()
    await dialog.getByRole('button', { name: 'Abrir caja' }).click()
    await expect(closed).toBeHidden()
  }
  await page.getByRole('button', { name: /^Medialuna\b/ }).first().click()
  await page.getByRole('button', { name: /COBRAR/ }).click()
  await page.getByRole('dialog', { name: 'Cobrar' }).getByRole('button', { name: /Confirmar cobro/ }).click()
  await expect(page.getByRole('dialog').getByText('¡Venta cobrada!')).toBeVisible()
}

test('the login screen tells the visitor which PIN to use', async ({ browser }) => {
  const ctx = await browser.newContext()
  try {
    const page = await openDemo(ctx)
    const hint = page.getByTestId('demo-login-hint')
    await expect(hint).toContainText('elegí un usuario')
    await page.getByRole('button', { name: new RegExp(OWNER.name) }).click()
    await expect(hint).toContainText(`PIN de la demo: ${OWNER.pin}`)
    // Typing exactly what the screen says gets the visitor in.
    for (const d of OWNER.pin) await page.getByRole('button', { name: d, exact: true }).click()
    await page.getByRole('button', { name: 'Entrar' }).click()
    await expect(page.getByRole('heading', { level: 1 })).toContainText('Dueño')
  } finally {
    await ctx.close()
  }
})

test('every visitor gets their own sandbox: sales never leak between browsers', async ({ browser }) => {
  const a = await browser.newContext()
  const b = await browser.newContext()
  try {
    const pageA = await openDemo(a)
    const pageB = await openDemo(b)

    const cookieA = (await a.cookies()).find((c) => c.name === 'bloom_demo')
    const cookieB = (await b.cookies()).find((c) => c.name === 'bloom_demo')
    expect(cookieA?.httpOnly).toBe(true)
    expect(cookieA?.sameSite).toBe('Lax')
    expect(cookieA?.value).toMatch(/^[0-9a-f]{32}$/)
    expect(cookieA?.value).not.toBe(cookieB?.value)

    // The banner is always there and explains the demo.
    await expect(pageA.getByTestId('demo-banner')).toHaveText(/Tu demo se borra en (1 h 5\d|2 h 00) min/)
    await pageA.getByTestId('demo-banner').click()
    await expect(pageA.getByText('PIN 1234')).toBeVisible()
    await pageA.keyboard.press('Escape')

    await login(pageA)
    await login(pageB)
    const token = (p: Page) => p.evaluate(() => localStorage.getItem('cafe.token'))
    const tickets = async (p: Page) => {
      const res = await p.request.get('/api/cash/current', { headers: { Authorization: `Bearer ${await token(p)}` } })
      expect(res.ok()).toBeTruthy()
      return ((await res.json()) as { tickets: number } | null)?.tickets ?? 0
    }
    const before = await tickets(pageB) // both start from the same demo data

    await sellMedialuna(pageA)
    expect(await tickets(pageA)).toBe(before + 1)
    expect(await tickets(pageB)).toBe(before) // A's sale never reaches B's sandbox
    await pageB.reload()
    await expect(pageB.getByTestId('demo-banner')).toBeVisible()
  } finally {
    await a.close()
    await b.close()
  }
})

test('features that reach outside the sandbox are off with a friendly message', async ({ browser }) => {
  const ctx = await browser.newContext()
  try {
    const page = await openDemo(ctx)
    await login(page)
    const auth = { Authorization: `Bearer ${await page.evaluate(() => localStorage.getItem('cafe.token'))}` }
    const res = await page.request.post('/api/system/backups', { headers: auth })
    expect(res.status()).toBe(403)
    expect((await res.json()).detail).toContain('desactivados en la demo')
    const lic = await (await page.request.get('/api/license', { headers: auth })).json()
    expect(lic.valid).toBe(true)
  } finally {
    await ctx.close()
  }
})


test('countdown, DEMO watermark on printed documents and the friendly end screen', async ({ browser }) => {
  const ctx = await browser.newContext()
  try {
    const page = await openDemo(ctx)
    await expect(page.getByTestId('demo-countdown')).toHaveText(/^Tu demo se borra en/)
    await page.getByTestId('demo-banner').click()
    await expect(page.getByText('lo que imprimas sale marcado como DEMO')).toBeVisible()
    await page.keyboard.press('Escape')
    await login(page)

    // Printed documents go through a hidden iframe: its content carries the watermark.
    await sellMedialuna(page)
    const printed = page.waitForEvent('frameattached')
    await page.getByRole('dialog').getByRole('button', { name: /Imprimir/ }).first().click()
    const frame = await printed
    await expect.poll(async () => (await frame.content()).includes('DEMO · datos de ejemplo')).toBe(true)
    if (process.env.BLOOM_SHOTS) await page.screenshot({ path: `${process.env.BLOOM_SHOTS}/demo-countdown.png` })

    // Time's up (the server says so): the end screen offers download / sign up / another demo.
    await page.route('**/api/health', async (route) => {
      const res = await route.fetch()
      const body = await res.json()
      body.demo = { ...body.demo, session: false, expires_in_s: null, ended: 'lifetime', signup_url: 'https://bloom.example.com/registro' }
      await route.fulfill({ response: res, json: body })
    })
    await page.reload()
    const end = page.getByRole('alertdialog', { name: 'Tu demo terminó' })
    await expect(end).toBeVisible()
    await expect(end.getByRole('link', { name: 'Descargá Bloom gratis' })).toHaveAttribute('href', 'https://bloom.example.com')
    await expect(end.getByRole('link', { name: 'Crear mi cuenta' })).toBeVisible()
    await expect(end.getByRole('link', { name: 'Empezar otra demo' })).toHaveAttribute('href', '/api/demo/new')
    if (process.env.BLOOM_SHOTS) await page.screenshot({ path: `${process.env.BLOOM_SHOTS}/demo-end-screen.png` })
  } finally {
    await ctx.close()
  }
})

test('exports carry DEMO and backups never leave the demo', async ({ browser }) => {
  const ctx = await browser.newContext()
  try {
    const page = await openDemo(ctx)
    await login(page)
    const auth = { Authorization: `Bearer ${await page.evaluate(() => localStorage.getItem('cafe.token'))}` }
    const csv = await page.request.get('/api/reports/sales?format=csv', { headers: auth })
    if (csv.status() !== 404) {
      expect(csv.headers()['content-disposition']).toContain('DEMO-reporte-')
      expect((await csv.text()).replace(/^﻿/, '')).toMatch(/^DEMO/)
    }
    expect((await page.request.get('/api/system/backups/x.db/download', { headers: auth })).status()).toBe(403)
  } finally {
    await ctx.close()
  }
})
