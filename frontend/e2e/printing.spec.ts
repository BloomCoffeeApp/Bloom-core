import net from 'node:net'

import type { Page } from '@playwright/test'

import { expect, test } from './fixtures'
import { authHeaders, cartLine, confirmCheckout, openCheckout, openPos, productTile, ticketNumber } from './helpers'

/**
 * Direct thermal printing (ESC/POS): the settings screen with a network printer that is really a
 * local TCP socket (the backend sends the raw bytes to it), the automatic ticket with the cash drawer,
 * and the fallbacks to the system print dialog (no printer, printer failure, not available).
 */

const main = (page: Page) => page.getByRole('main').last()

/** A fake network thermal printer: a TCP server on 127.0.0.1 collecting what it receives. */
async function fakePrinter() {
  const chunks: Buffer[] = []
  const server = net.createServer((sock) => sock.on('data', (d) => chunks.push(d)))
  await new Promise<void>((r) => server.listen(0, '127.0.0.1', r))
  const port = (server.address() as net.AddressInfo).port
  return {
    port,
    bytes: () => Buffer.concat(chunks),
    text: () => Buffer.concat(chunks).toString('latin1'),
    clear: () => void chunks.splice(0),
    close: () => new Promise<void>((r) => server.close(() => r())),
  }
}

/** Counts the hidden iframes `printHtml` creates (= the system print dialog was opened). */
async function trackPrintDialogs(page: Page) {
  await page.addInitScript(() => {
    const w = window as unknown as { __printFrames: number }
    w.__printFrames = 0
    new MutationObserver((muts) => {
      for (const m of muts)
        for (const n of m.addedNodes) if (n instanceof HTMLIFrameElement && n.getAttribute('aria-hidden') === 'true') w.__printFrames++
    }).observe(document, { childList: true, subtree: true })
  })
}
const printDialogs = (page: Page) => page.evaluate(() => (window as unknown as { __printFrames: number }).__printFrames)

async function resetPrinting(page: Page) {
  const res = await page.request.put('/api/printing/config', {
    data: { printers: [], cashier_printer: null, ticket_mode: 'ask', cash_drawer: false, drawer_pin: 0, stations: {} },
    headers: await authHeaders(page),
  })
  expect(res.ok(), await res.text()).toBeTruthy()
}

async function sellMedialuna(page: Page) {
  await openPos(page)
  await productTile(page, 'Medialuna').click()
  await expect(cartLine(page, 'Medialuna')).toBeVisible()
  const done = await confirmCheckout(page, await openCheckout(page))
  return { done, number: await ticketNumber(done) }
}

test.describe('Impresión directa (ESC/POS)', () => {
  test('network printer: test page, saved settings and automatic ticket with the cash drawer', async ({ page, errors }) => {
    const printer = await fakePrinter()
    await trackPrintDialogs(page)
    await page.goto('/config?tab=impresoras')
    await resetPrinting(page)
    try {
      await page.reload()
      await expect(main(page).getByText('Sin impresoras térmicas')).toBeVisible()
      await main(page).getByRole('button', { name: 'Agregar impresora' }).click()
      const row = main(page).getByTestId('printer-row')
      await row.getByRole('radio', { name: 'De red (IP)' }).click()
      await row.getByLabel('Dirección IP').fill('127.0.0.1')
      await row.getByLabel('Puerto').fill(String(printer.port))
      await row.getByRole('radio', { name: '58 mm' }).click()
      await expect(row.getByLabel('Caracteres por línea')).toHaveValue('32')

      await row.getByRole('button', { name: 'Imprimir prueba' }).click()
      await expect(page.getByText('Se mandó la prueba a «Caja»')).toBeVisible()
      await expect.poll(() => printer.text()).toContain('Prueba de impresi')
      expect(printer.bytes().subarray(0, 2).toString('latin1')).toBe('\x1b@') // ESC @ (init)
      expect(printer.text()).toContain('12345678901234567890123456789012\n') // 32 columns

      // The first printer becomes the cashier's; automatic ticket + drawer.
      await expect(main(page).getByRole('combobox', { name: 'Impresora de la caja' })).toContainText('Caja')
      await main(page).getByRole('radio', { name: 'Automático' }).click()
      await main(page).getByRole('switch', { name: 'Abrir el cajón en ventas en efectivo' }).click()
      await main(page).getByRole('button', { name: 'Guardar' }).click()
      await expect(page.getByText('Impresoras guardadas')).toBeVisible()
      await page.reload()
      await expect(main(page).getByTestId('printer-row').getByLabel('Dirección IP')).toHaveValue('127.0.0.1')
      await expect(main(page).getByRole('radio', { name: 'Automático' })).toHaveAttribute('aria-checked', 'true')
      await expect(main(page).getByRole('switch', { name: 'Abrir el cajón en ventas en efectivo' })).toHaveAttribute('aria-checked', 'true')

      // A cash sale prints by itself on the thermal printer, drawer kick first; no print dialog.
      printer.clear()
      const { number } = await sellMedialuna(page)
      await expect.poll(() => printer.text()).toContain(`Ticket #${number}`)
      expect(printer.text()).toContain('\x1bp\x00') // ESC p 0 (drawer, pin 2)
      expect(printer.text()).toContain('Medialuna')
      expect(await printDialogs(page)).toBe(0)
      expect(errors.consoleErrors).toEqual([])
    } finally {
      await resetPrinting(page)
      await printer.close()
    }
  })

  test('printer failure: clear message and the system print dialog (ticket and Z)', async ({ page }) => {
    await trackPrintDialogs(page)
    const detail = 'No se pudo imprimir en «Caja»: La impresora 10.0.0.9:9100 no respondió.'
    await page.route('**/api/printing/status', (r) =>
      r.fulfill({ json: { available: true, reason: null, ticket_mode: 'auto', cashier: true, cash_drawer: false } }),
    )
    await page.route('**/api/printing/sales/*/ticket', (r) => r.fulfill({ status: 502, json: { detail } }))
    await page.route('**/api/printing/cash-sessions/*/z', (r) => r.fulfill({ status: 502, json: { detail } }))

    await sellMedialuna(page)
    await expect(page.getByText(`${detail}. Se abrió el diálogo de impresión del sistema.`)).toBeVisible()
    await expect.poll(() => printDialogs(page)).toBe(1)

    await page.goto('/caja')
    await page.getByRole('tab', { name: /Historial de cierres/ }).click()
    await page.getByRole('row').filter({ hasText: /#\d+/ }).first().click()
    const z = page.getByRole('dialog', { name: /Cierre de caja #\d+/ })
    await z.getByRole('button', { name: 'Imprimir Z' }).click()
    await expect(page.getByText(`${detail}. Se abrió el diálogo de impresión del sistema.`).first()).toBeVisible()
    await expect.poll(() => printDialogs(page)).toBe(1) // counter restarts with the page load
  })

  test('no thermal printer: the ticket goes to the print dialog quietly; "nunca" hides the button', async ({ page }) => {
    await trackPrintDialogs(page)
    await page.goto('/pos')
    await resetPrinting(page)
    const direct: string[] = []
    page.on('request', (req) => {
      if (/\/api\/printing\/(sales|cash-sessions)\//.test(req.url())) direct.push(req.url())
    })
    const { done } = await sellMedialuna(page)
    expect(await printDialogs(page)).toBe(0) // "preguntar" (default): nothing automatic
    await done.getByRole('button', { name: 'Imprimir ticket' }).click()
    await expect.poll(() => printDialogs(page)).toBe(1)
    expect(direct).toEqual([])
    await done.getByRole('button', { name: 'Nueva venta' }).click()

    await page.route('**/api/printing/status', (r) =>
      r.fulfill({ json: { available: true, reason: null, ticket_mode: 'never', cashier: false, cash_drawer: false } }),
    )
    await page.reload()
    const again = await sellMedialuna(page)
    await expect(again.done.getByRole('button', { name: 'Nueva venta' })).toBeVisible()
    await expect(again.done.getByRole('button', { name: 'Imprimir ticket' })).toHaveCount(0)
  })

  test('not available (demo or outside Windows): the settings explain it', async ({ page }) => {
    await page.route('**/api/printing/config', (r) =>
      r.fulfill({
        json: {
          printers: [], cashier_printer: null, ticket_mode: 'ask', cash_drawer: false, drawer_pin: 0, stations: {},
          available: false, reason: 'La impresión directa está disponible solo en Windows: se usa el diálogo de impresión.',
          station_list: [],
        },
      }),
    )
    await page.goto('/config?tab=impresoras')
    await expect(main(page).getByTestId('printing-unavailable')).toContainText('disponible solo en Windows')
    await expect(main(page).getByRole('button', { name: 'Agregar impresora' })).toHaveCount(0)
  })
})
