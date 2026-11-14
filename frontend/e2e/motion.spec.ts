import { ensureCashOpen, expect, test } from './fixtures'

/** Motion tokens (index.css) and the global prefers-reduced-motion guard. */

const secs = (v: string) => parseFloat(v) * (v.endsWith('ms') ? 0.001 : 1)

async function openCheckout(page: import('@playwright/test').Page) {
  await page.goto('/pos')
  await ensureCashOpen(page)
  await page.getByRole('button', { name: /Medialuna/ }).first().click()
  await page.getByRole('button', { name: /COBRAR/ }).click()
  const dialog = page.getByRole('dialog', { name: 'Cobrar' })
  await expect(dialog).toBeVisible()
  return dialog
}

/** A throwaway element with the given utility classes, to read what the CSS resolves to. */
function probe(page: import('@playwright/test').Page, cls: string) {
  return page.evaluate((c) => {
    const el = document.createElement('div')
    el.className = c
    document.body.appendChild(el)
    const s = getComputedStyle(el)
    const out = { duration: s.animationDuration, count: s.animationIterationCount, tDuration: s.transitionDuration }
    el.remove()
    return out
  }, cls)
}

test.describe('motion', () => {
  test('dialogs use the motion tokens', async ({ page }) => {
    const dialog = await openCheckout(page)
    const d = await dialog.evaluate((el) => getComputedStyle(el).animationDuration)
    expect(secs(d)).toBeCloseTo(0.18, 2)
    const root = await page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue('--motion-base').trim())
    expect(root).toBe('180ms')
  })

  test('reduced motion: animations are ~instant and loops stop, loaders keep spinning', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' })
    const dialog = await openCheckout(page)
    const d = await dialog.evaluate((el) => getComputedStyle(el).animationDuration)
    expect(secs(d)).toBeLessThan(0.001)

    const pulse = await probe(page, 'animate-pulse')
    expect(pulse.count).toBe('1')
    expect(secs(pulse.duration)).toBeLessThan(0.001)

    const ping = await probe(page, 'animate-ping')
    expect(ping.count).toBe('1')

    const spin = await probe(page, 'animate-spin')
    expect(spin.count).toBe('infinite')
    expect(secs(spin.duration)).toBeGreaterThan(0.5)
  })

  test('normal motion: loops are untouched', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'no-preference' })
    await page.goto('/')
    const pulse = await probe(page, 'animate-pulse')
    expect(pulse.count).toBe('infinite')
  })

  test('cart lines enter with a fade and the total bumps when it changes', async ({ page }) => {
    await page.goto('/pos')
    await ensureCashOpen(page)
    await page.getByRole('button', { name: /Medialuna/ }).first().click()
    const line = page.getByTestId('cart-line').first()
    await expect(line).toBeVisible()
    expect(await line.evaluate((el) => getComputedStyle(el).animationName)).toContain('motion-enter')
    await page.getByRole('button', { name: /Medialuna/ }).first().click()
    await expect(page.locator('[class*="motion-bump"]').first()).toBeAttached()
  })
  test('entrance animations leave nothing behind (a filling animation would trap fixed overlays under the header)', async ({ page }) => {
    await page.goto('/')
    await expect
      .poll(() => page.evaluate(() => document.querySelector('main > div')?.getAnimations().length ?? -1))
      .toBe(0)
  })
})
