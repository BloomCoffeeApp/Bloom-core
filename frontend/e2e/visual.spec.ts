import { ensureCashOpen, expect, test } from './fixtures'

/**
 * Visual regression: the key screens in light and dark, desktop and phone, compared against approved
 * screenshots (`e2e/visual.spec.ts-snapshots/`). A diff means the screen changed: if it was intended, approve it with
 *
 *     npx playwright test e2e/visual.spec.ts --update-snapshots
 *
 * and look at the changed PNGs in the diff before committing. Only screens whose content is stable (fixed demo
 * data, no relative dates) are covered.
 *
 * It runs on its OWN, with a fresh database (`npm run e2e:visual`): inside the full suite the other specs create
 * products and sales first, so the screens no longer look like the approved ones. That is why it is skipped
 * unless E2E_VISUAL=1.
 */
test.skip(!process.env.E2E_VISUAL, 'visual regression runs on its own: npm run e2e:visual')

const SCREENS: { name: string; path: string; ready: (p: import('@playwright/test').Page) => Promise<void> }[] = [
  { name: 'pos', path: '/pos', ready: async (p) => { await ensureCashOpen(p) } },
  { name: 'productos', path: '/productos', ready: async (p) => { await expect(p.getByRole('heading', { level: 1, name: 'Productos' })).toBeVisible() } },
  { name: 'config', path: '/config', ready: async (p) => { await expect(p.getByRole('heading', { level: 1, name: 'Configuración' })).toBeVisible() } },
]

const THEMES = ['light', 'dark'] as const

for (const theme of THEMES) {
  test.describe(`visual: ${theme}`, () => {
    test.use({ colorScheme: theme })

    for (const s of SCREENS) {
      test(`${s.name} (desktop)`, async ({ page }) => {
        await page.addInitScript((t) => localStorage.setItem('cafe.theme', t), theme)
        await page.goto(s.path)
        await s.ready(page)
        await page.waitForLoadState('networkidle')
        await expect(page).toHaveScreenshot(`${s.name}-${theme}-desktop.png`, { maxDiffPixelRatio: 0.002, threshold: 0.1, animations: 'disabled', caret: 'hide' })
      })
    }

    test('pos (phone)', async ({ page }) => {
      await page.setViewportSize({ width: 390, height: 844 })
      await page.addInitScript((t) => localStorage.setItem('cafe.theme', t), theme)
      await page.goto('/pos')
      await ensureCashOpen(page)
      await page.waitForLoadState('networkidle')
      await expect(page).toHaveScreenshot(`pos-${theme}-phone.png`, { maxDiffPixelRatio: 0.002, threshold: 0.1, animations: 'disabled', caret: 'hide' })
    })
  })
}
