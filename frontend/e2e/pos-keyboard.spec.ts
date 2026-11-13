import { ensureCashOpen, expect, test } from './fixtures'

/** The POS must be usable with the keyboard alone (cashiers do it all day): no mouse after the page opens. */
test.describe('POS with the keyboard only', () => {
  test('F2 search, Enter adds, F9 charges, Enter confirms', async ({ page }) => {
    await page.goto('/pos')
    await ensureCashOpen(page)
    await page.locator('body').click({ position: { x: 1, y: 1 } }) // only to leave focus on the page, not on a control

    await page.keyboard.press('F2')
    const search = page.getByRole('textbox', { name: 'Buscar producto' })
    await expect(search).toBeFocused()

    await page.keyboard.type('Medialuna')
    await page.keyboard.press('Enter')
    await expect(search).toHaveValue('') // the first match went to the cart and the box is ready for the next one
    await expect(page.getByRole('button', { name: /COBRAR/ })).toBeEnabled()

    await page.keyboard.press('F9')
    const dialog = page.getByRole('dialog', { name: 'Cobrar' })
    await expect(dialog).toBeVisible()
    await page.keyboard.press('Enter')
    await expect(page.getByRole('dialog').getByText('¡Venta cobrada!')).toBeVisible()
  })

  test('the checkout dialog traps focus and Escape returns to the POS', async ({ page }) => {
    await page.goto('/pos')
    await ensureCashOpen(page)
    await page.keyboard.press('F2')
    await page.keyboard.type('Medialuna')
    await page.keyboard.press('Enter')
    await page.keyboard.press('F9')
    const dialog = page.getByRole('dialog', { name: 'Cobrar' })
    await expect(dialog).toBeVisible()

    // Tab many times: focus must never leave the dialog.
    for (let i = 0; i < 25; i++) {
      await page.keyboard.press('Tab')
      const inside = await page.evaluate(() => !!document.activeElement?.closest('[role="dialog"]'))
      expect(inside, `focus escaped the dialog on Tab #${i + 1}`).toBe(true)
    }

    await page.keyboard.press('Escape')
    await expect(dialog).toBeHidden()
    await page.keyboard.press('F2') // and the shortcuts work again
    await expect(page.getByRole('textbox', { name: 'Buscar producto' })).toBeFocused()
  })

  test('every control reachable by Tab shows a visible focus indicator', async ({ page }) => {
    await page.goto('/pos')
    await ensureCashOpen(page)
    await page.keyboard.press('F2')
    const missing: string[] = []
    let checked = 0
    for (let i = 0; i < 20; i++) {
      await page.keyboard.press('Tab')
      const info = await page.evaluate(() => {
        const el = document.activeElement as HTMLElement | null
        if (!el || el === document.body) return null
        const cs = getComputedStyle(el)
        const outline = cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) > 0
        const ring = cs.boxShadow !== 'none' && cs.boxShadow !== ''
        const border = el.matches(':focus-visible') && cs.borderColor !== ''
        return { label: (el.getAttribute('aria-label') || el.textContent || el.tagName).trim().slice(0, 30), visible: outline || ring || border }
      })
      if (info) checked++
      if (info && !info.visible) missing.push(info.label)
    }
    expect(checked, 'Tab should reach many controls').toBeGreaterThan(8)
    expect(missing, 'focusable controls without a visible focus indicator').toEqual([])
  })
})
