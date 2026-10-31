import type { Page } from '@playwright/test'

import { USERS } from './constants'
import { addMedialuna, ensureCashOpen, expect, test } from './fixtures'

const noHorizontalOverflow = (page: Page) =>
  page.evaluate(() => document.scrollingElement!.scrollWidth <= window.innerWidth)

test.describe('phone', () => {
  test.describe('login', () => {
    test.use({ storageState: { cookies: [], origins: [] } })

    test('PIN pad by touch', async ({ page }) => {
      await page.addInitScript(() => {
        for (let i = 1; i <= 100; i++) localStorage.setItem(`bloom.tour.done.${i}`, '1')
      })
      await page.goto('/')
      await page.getByRole('button', { name: new RegExp(USERS.caja.name) }).tap()
      for (const d of USERS.caja.pin) await page.getByRole('button', { name: d, exact: true }).tap()
      await page.getByRole('button', { name: 'Entrar' }).tap()
      await expect(page.getByRole('button', { name: 'Bloquear' })).toBeVisible()
      expect(await noHorizontalOverflow(page)).toBe(true)
    })
  })

  test('the sidebar opens as a sheet from the header and navigates', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
    await page.locator('header').getByRole('button', { name: 'Toggle Sidebar' }).tap()
    const sheet = page.getByRole('dialog', { name: 'Sidebar' })
    await expect(sheet).toBeVisible()
    await sheet.getByRole('link', { name: 'Stock' }).tap()
    await expect(page).toHaveURL(/\/stock$/)
    await expect(page.getByRole('heading', { level: 1, name: 'Stock' })).toBeVisible()
    await expect(sheet).toBeHidden()
  })

  test('dashboard is readable without horizontal scroll', async ({ page, errors }) => {
    await page.goto('/')
    await expect(page.getByText('Ticket promedio', { exact: true })).toBeVisible()
    await page.waitForLoadState('networkidle')
    expect(await noHorizontalOverflow(page)).toBe(true)
    expect(errors.consoleErrors).toEqual([])
  })

  test('POS: add a product and reach the checkout', async ({ page }) => {
    await page.goto('/pos')
    await ensureCashOpen(page)
    await page.getByRole('button', { name: /^Medialuna\b/ }).first().tap()
    await expect(page.getByText(/Subtotal · \d+ ítem/)).toBeVisible()
    // Products and cart stacked, both fully inside the screen (no clipped columns)
    const width = page.viewportSize()!.width
    const cobrar = page.getByRole('button', { name: /COBRAR/ })
    for (const el of [page.getByRole('textbox', { name: 'Buscar producto' }), cobrar]) {
      const box = (await el.boundingBox())!
      expect(box.x).toBeGreaterThanOrEqual(0)
      expect(box.x + box.width).toBeLessThanOrEqual(width + 1)
    }
    await expect(cobrar).toBeInViewport({ ratio: 1 })
    await cobrar.tap()
    const dialog = page.getByRole('dialog', { name: 'Cobrar' })
    await expect(dialog.getByRole('button', { name: /Confirmar cobro/ })).toBeVisible()
    expect(await noHorizontalOverflow(page)).toBe(true)

    // Courtesy toggle by touch: payment inputs go away, the confirm button fits the screen.
    await page.getByRole('switch', { name: 'Cortesía (no se cobra)' }).tap()
    const courtesy = page.getByRole('dialog', { name: 'Cortesía' })
    const register = courtesy.getByRole('button', { name: 'Registrar cortesía' })
    await register.scrollIntoViewIfNeeded()
    await expect(register).toBeInViewport({ ratio: 1 })
    expect((await register.boundingBox())!.height).toBeGreaterThanOrEqual(44)
    await expect(courtesy.getByRole('button', { name: /Confirmar cobro/ })).toHaveCount(0)
    expect(await noHorizontalOverflow(page)).toBe(true)
  })

  test('settings tabs are reachable', async ({ page }) => {
    await page.goto('/config')
    for (const tab of ['Negocio', 'Usuarios', 'Seguridad', 'Respaldo', 'Apariencia', 'Acerca de']) {
      const t = page.getByRole('tab', { name: tab, exact: true })
      await t.scrollIntoViewIfNeeded()
      await t.tap()
      await expect(t).toHaveAttribute('aria-selected', 'true')
    }
    expect(await noHorizontalOverflow(page)).toBe(true)
  })
})

test.describe('tablet', () => {
  test.use({ viewport: { width: 768, height: 1024 } })

  test('POS layout: products and cart side by side', async ({ page }) => {
    await page.goto('/pos')
    await ensureCashOpen(page)
    await addMedialuna(page)
    const search = await page.getByRole('textbox', { name: 'Buscar producto' }).boundingBox()
    const cobrar = await page.getByRole('button', { name: /COBRAR/ }).boundingBox()
    expect(search && cobrar).toBeTruthy()
    expect(cobrar!.x).toBeGreaterThan(search!.x + search!.width - 1) // cart column to the right
    expect(cobrar!.y + cobrar!.height).toBeLessThanOrEqual(1024)
    expect(await noHorizontalOverflow(page)).toBe(true)
    await page.getByRole('button', { name: /COBRAR/ }).tap()
    await expect(page.getByRole('dialog', { name: 'Cobrar' })).toBeVisible()
  })
})
