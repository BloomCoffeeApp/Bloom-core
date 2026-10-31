import { expect, isResponsive, test } from './fixtures'
import { statCard } from './helpers'

test('dashboard KPIs render and the date presets change the data', async ({ page, errors }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Admin')
  const main = page.getByRole('main').last()
  for (const label of ['Ventas', 'Tickets', 'Ticket promedio', 'Margen bruto estimado'])
    await expect(statCard(main, label)).toBeVisible()
  for (const panel of ['Ventas por hora', 'Últimos 30 días', 'Top 10 productos', 'Medios de pago', 'Últimos tickets'])
    await expect(main.getByText(panel, { exact: true })).toBeVisible()

  const tickets = statCard(main, 'Tickets').locator('p').nth(1)
  const read = async (preset: string) => {
    await page.getByRole('radio', { name: preset, exact: true }).click()
    await expect(page.getByRole('radio', { name: preset, exact: true })).toHaveAttribute('aria-checked', 'true')
    await expect(statCard(main, 'Tickets').locator('[data-slot="skeleton"]')).toHaveCount(0)
    return Number((await tickets.innerText()).replace(/\D/g, ''))
  }

  const week = await read('7 días')
  const month = await read('30 días')
  await read('Ayer')
  await read('Mes')
  const today = await read('Hoy')
  // 90 days of demo sales: a month has more tickets than a week, and a week at least as many as today
  expect(month).toBeGreaterThan(week)
  expect(week).toBeGreaterThanOrEqual(today)

  expect(await isResponsive(page)).toBe(true)
  expect(errors.consoleErrors).toEqual([])
})
