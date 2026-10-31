import { fmtDateTime, fmtMoney, fmtNumber } from '@/lib/format'

import { esc, printHtml } from '../sales/print'
import type { CashSessionDetail } from './types'

const signed = (c: number | null) => (c == null ? '—' : `${c > 0 ? '+' : ''}${fmtMoney(c)}`)

export function printZReport(s: CashSessionDetail) {
  const methods = s.by_method
    .map(
      (m) => `<tr><td>${esc(m.name)}</td><td class="r">${esc(fmtMoney(m.sales_cents))}</td><td class="r">${esc(fmtMoney(m.expected_cents))}</td>` +
        `<td class="r">${esc(m.counted_cents == null ? '—' : fmtMoney(m.counted_cents))}</td><td class="r">${esc(signed(m.difference_cents))}</td></tr>`,
    )
    .join('')
  const cats = s.by_category
    .map((c) => `<div class="row"><span>${esc(c.name)} (${esc(fmtNumber(c.qty))})</span><span>${esc(fmtMoney(c.total_cents))}</span></div>`)
    .join('')
  const movs = s.movements
    .map((m) => `<div class="row s"><span>${m.type === 'in' ? 'Ingreso' : 'Egreso'} · ${esc(m.reason)}</span><span>${m.type === 'in' ? '' : '-'}${esc(fmtMoney(m.amount_cents))}</span></div>`)
    .join('')
  const body = `
    <h1>${esc(s.business?.name || 'Cafetería')}</h1>
    <div class="c b">CIERRE DE CAJA (Z) · #${esc(s.id)}</div>
    <hr/>
    <div class="row s"><span>Apertura</span><span>${esc(fmtDateTime(s.opened_at))} · ${esc(s.opened_by_name ?? '')}</span></div>
    <div class="row s"><span>Cierre</span><span>${esc(s.closed_at ? fmtDateTime(s.closed_at) : 'Abierta')}${s.closed_by_name ? ` · ${esc(s.closed_by_name)}` : ''}</span></div>
    <hr/>
    <div class="row"><span>Fondo inicial</span><span>${esc(fmtMoney(s.opening_cents))}</span></div>
    <div class="row"><span>Tickets</span><span>${esc(s.tickets)}</span></div>
    <div class="row"><span>Ticket promedio</span><span>${esc(fmtMoney(s.avg_ticket_cents))}</span></div>
    <div class="row"><span>Descuentos</span><span>${esc(fmtMoney(s.discounts_cents))}</span></div>
    <div class="row"><span>Anulaciones (${esc(s.voided_count)})</span><span>${esc(fmtMoney(s.voided_total_cents))}</span></div>
    <div class="row big"><span>VENTAS</span><span>${esc(fmtMoney(s.sales_total_cents))}</span></div>
    <hr/>
    <div class="b">Arqueo por medio de pago</div>
    <table class="s"><tr><th>Medio</th><th class="r">Ventas</th><th class="r">Esper.</th><th class="r">Contado</th><th class="r">Dif.</th></tr>${methods}</table>
    <div class="row b"><span>Diferencia total</span><span>${esc(signed(s.difference_cents))}</span></div>
    <hr/>
    <div class="b">Movimientos de caja</div>
    ${movs || '<div class="s">Sin movimientos</div>'}
    <div class="row s"><span>Ingresos / Egresos</span><span>${esc(fmtMoney(s.movements_in_cents))} / -${esc(fmtMoney(s.movements_out_cents))}</span></div>
    <hr/>
    <div class="b">Ventas por categoría</div>
    ${cats || '<div class="s">Sin ventas</div>'}
    ${s.notes ? `<hr/><div class="s">Obs.: ${esc(s.notes)}</div>` : ''}
    <hr/><div class="c s">Impreso ${esc(fmtDateTime(new Date()))}</div>
  `
  printHtml(`Cierre Z #${s.id}`, body)
}
