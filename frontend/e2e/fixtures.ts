import { type ConsoleMessage, expect, type Page, test as base } from '@playwright/test'

export { expect }
/** Re-exported for the Pro specs (their real path can't resolve @playwright/test). */
export { devices } from '@playwright/test'

/** Console messages that are expected noise, not app bugs. */
const IGNORED_CONSOLE = [/Download the React DevTools/i, /\[vite\]/i]

export interface ErrorLog {
  /** Uncaught exceptions in the page. */
  pageErrors: string[]
  /** console.error messages (minus known noise). */
  consoleErrors: string[]
}

/** Every test fails on uncaught page exceptions; `errors` exposes console errors for stricter checks. */
export const test = base.extend<{ errors: ErrorLog }>({
  errors: [
    async ({ page }, use) => {
      const log: ErrorLog = { pageErrors: [], consoleErrors: [] }
      page.on('pageerror', (e) => log.pageErrors.push(`${e.name}: ${e.message}`))
      page.on('console', (m: ConsoleMessage) => {
        if (m.type() !== 'error') return
        const text = m.text()
        if (IGNORED_CONSOLE.some((r) => r.test(text))) return
        log.consoleErrors.push(text)
      })
      await use(log)
      expect(log.pageErrors, 'uncaught exceptions in the page').toEqual([])
    },
    { auto: true },
  ],
})

/** Resolves true if the page's main thread answers within `ms` (false = frozen, e.g. a render loop). */
export async function isResponsive(page: Page, ms = 3_000) {
  return Promise.race([
    page.evaluate(() => new Promise<boolean>((r) => requestAnimationFrame(() => r(true)))),
    new Promise<boolean>((r) => setTimeout(() => r(false), ms)),
  ])
}

/** Logs in through the PIN screen (keypad clicks + "Entrar"). */
export async function loginWithPin(page: Page, userName: string, pin: string) {
  await page.goto('/')
  await page.getByRole('button', { name: new RegExp(userName) }).click()
  await enterPin(page, pin)
}

export async function enterPin(page: Page, pin: string) {
  for (const d of pin) await page.getByRole('button', { name: d, exact: true }).click()
  await page.getByRole('button', { name: 'Entrar' }).click()
}

/** On /pos: opens the cash session if it's closed. */
export async function ensureCashOpen(page: Page) {
  const closed = page.getByText('La caja está cerrada')
  const checkout = page.getByRole('button', { name: /COBRAR/ })
  await expect(closed.or(checkout).first()).toBeVisible()
  // The overlay only appears once the cash query resolved; give it a moment.
  await page.waitForLoadState('networkidle')
  if (await closed.isVisible()) {
    await page.getByRole('button', { name: 'Abrir caja' }).click()
    const dialog = page.getByRole('dialog', { name: /Abrir caja/ })
    await dialog.getByRole('button', { name: /\$/ }).first().click()
    await dialog.getByRole('button', { name: 'Abrir caja' }).click()
    await expect(closed).toBeHidden()
  }
}

/** Adds a product without modifiers to the POS cart. */
export async function addMedialuna(page: Page) {
  await page.getByRole('button', { name: /^Medialuna\b/ }).first().click()
}
