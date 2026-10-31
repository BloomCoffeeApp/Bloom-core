import { toast } from 'sonner'

import { fmtDateTime, fmtMoney, fmtNumber } from '@/lib/format'

import { fetchTicket } from './api'
import { CHANNEL_LABEL, type TicketData } from './types'

export const esc = (s: unknown) =>
  String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!)

// Print documents are standalone pages rendered by the system print dialog; they use plain
// black-on-white (thermal printers) instead of the app's theme tokens.
const RECEIPT_CSS = `
  @page { size: 80mm auto; margin: 0; }
  * { box-sizing: border-box; }
  body { margin: 0; padding: 4mm 4mm 8mm; width: 80mm; font: 12px/1.35 ui-monospace, 'Cascadia Mono', Consolas, monospace; color: black; background: white; }
  h1 { font-size: 16px; margin: 0 0 2px; text-align: center; }
  .c { text-align: center; } .r { text-align: right; } .b { font-weight: 700; } .s { font-size: 10px; }
  .row { display: flex; justify-content: space-between; gap: 6px; }
  .row > span:first-child { flex: 1; min-width: 0; }
  hr { border: 0; border-top: 1px dashed black; margin: 6px 0; }
  .big { font-size: 16px; font-weight: 700; }
  .mod { padding-left: 10px; font-size: 11px; }
  .void { border: 2px solid black; text-align: center; font-weight: 700; padding: 4px; margin: 6px 0; font-size: 14px; }
  table { width: 100%; border-collapse: collapse; } td, th { padding: 1px 0; text-align: left; } td.r, th.r { text-align: right; }
`

/** Prints an HTML document through a hidden iframe (works in the desktop webview too). */
export function printHtml(title: string, body: string, css = RECEIPT_CSS) {
  const frame = document.createElement('iframe')
  frame.setAttribute('aria-hidden', 'true')
  Object.assign(frame.style, { position: 'fixed', right: '0', bottom: '0', width: '0', height: '0', border: '0' })
  document.body.appendChild(frame)
  const doc = frame.contentDocument
  if (!doc) {
    frame.remove()
    toast.error('No se pudo preparar la impresión')
    return
  }
  doc.open()
  doc.write(`<!doctype html><html lang="es"><head><meta charset="utf-8"><title>${esc(title)}</title><style>${css}</style></head><body>${body}</body></html>`)
  doc.close()
  const run = () => {
    try {
      frame.contentWindow?.focus()
      frame.contentWindow?.print()
    } finally {
      setTimeout(() => frame.remove(), 1500)
    }
  }
  setTimeout(run, 150)
}

export function ticketHtml({ business, sale, payment_names }: TicketData) {
  const lines = sale.items
    .map((it) => {
      const mods = (it.modifiers ?? [])
        .map((m) => `<div class="mod">+ ${esc(m.name)}${m.price_delta_cents ? ` (${esc(fmtMoney(m.price_delta_cents))})` : ''}</div>`)
        .join('')
      const note = it.notes ? `<div class="mod">» ${esc(it.notes)}</div>` : ''
      const disc = it.discount_cents && !sale.is_courtesy ? `<div class="row mod"><span>Desc.</span><span>-${esc(fmtMoney(it.discount_cents))}</span></div>` : ''
      return `<div class="row"><span>${esc(fmtNumber(it.qty))} x ${esc(it.name_snapshot)}</span><span>${esc(fmtMoney(it.total_cents + it.discount_cents))}</span></div>${mods}${note}${disc}`
    })
    .join('')
  const manualDisc = sale.discount_cents - sale.points_discount_cents
  const pays = sale.payments
    .map(
      (p) =>
        `<div class="row"><span>${esc(payment_names[p.method] ?? p.method)}</span><span>${esc(fmtMoney(p.amount_cents))}</span></div>` +
        (p.tendered_cents != null
          ? `<div class="row s"><span>Entregó</span><span>${esc(fmtMoney(p.tendered_cents))}</span></div><div class="row s"><span>Vuelto</span><span>${esc(fmtMoney(p.change_cents))}</span></div>`
          : ''),
    )
    .join('')
  return `
    <h1>${esc(business.name || 'Cafetería')}</h1>
    ${business.address ? `<div class="c s">${esc(business.address)}</div>` : ''}
    ${business.phone ? `<div class="c s">Tel. ${esc(business.phone)}</div>` : ''}
    ${business.cuit ? `<div class="c s">CUIT ${esc(business.cuit)}</div>` : ''}
    <hr/>
    <div class="row b"><span>Ticket #${esc(sale.number)}</span><span>${esc(fmtDateTime(sale.ts))}</span></div>
    <div class="row s"><span>${esc(CHANNEL_LABEL[sale.channel] ?? sale.channel)}${sale.table_label ? ` · Mesa ${esc(sale.table_label)}` : ''}</span><span>${esc(sale.user_name ?? '')}</span></div>
    ${sale.customer ? `<div class="s">Cliente: ${esc(sale.customer.name)}</div>` : ''}
    ${sale.status === 'voided' ? `<div class="void">ANULADO</div>` : ''}
    ${sale.is_courtesy ? `<div class="c b">CORTESÍA · INVITA LA CASA</div>${sale.courtesy_reason ? `<div class="c s">${esc(sale.courtesy_reason)}</div>` : ''}` : ''}
    <hr/>
    ${lines}
    <hr/>
    <div class="row"><span>Subtotal</span><span>${esc(fmtMoney(sale.subtotal_cents))}</span></div>
    ${manualDisc > 0 ? `<div class="row"><span>Descuento</span><span>-${esc(fmtMoney(manualDisc))}</span></div>` : ''}
    ${sale.points_discount_cents > 0 ? `<div class="row"><span>Canje ${esc(sale.points_redeemed)} pts</span><span>-${esc(fmtMoney(sale.points_discount_cents))}</span></div>` : ''}
    <div class="row big"><span>TOTAL</span><span>${esc(fmtMoney(sale.total_cents))}</span></div>
    <hr/>
    ${pays}
    ${sale.points_earned ? `<hr/><div class="s">Sumaste ${esc(sale.points_earned)} puntos${sale.customer ? ` · Total: ${esc(sale.customer.points)}` : ''}</div>` : ''}
    <hr/>
    <div class="c s">${esc(business.ticket_footer || '¡Gracias por tu visita!')}</div>
    <div class="c s">Comprobante no válido como factura</div>
  `
}

export async function printTicket(saleId: number) {
  try {
    const data = await fetchTicket(saleId)
    printHtml(`Ticket ${data.sale.number}`, ticketHtml(data))
  } catch (e) {
    toast.error((e as Error).message)
  }
}
