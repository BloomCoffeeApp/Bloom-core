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
    await expect(pageA.getByTestId('demo-banner')).toHaveText(/Demo: los datos se borran solos/)
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
