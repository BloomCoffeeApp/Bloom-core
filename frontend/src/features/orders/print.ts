import { fmtNumber, fmtTime } from '@/lib/format'

import { esc, printHtml } from '../sales/print'
import { CHANNEL_LABEL } from '../sales/types'
import type { Order } from './types'

/** Kitchen ticket ("comanda") of one order for a station's printer (80 mm). */
export function printKitchenTicket(o: Order, stationName: string | null) {
  const items = o.items
    .map((it) => {
      const mods = it.modifiers.map((m) => `<div class="mod">+ ${esc(m)}</div>`).join('')
      const note = it.notes ? `<div class="mod b">» ${esc(it.notes)}</div>` : ''
      const size = it.size_name ? ` (${esc(it.size_name)})` : ''
      return `<div class="big">${esc(fmtNumber(it.qty, 1))} × ${esc(it.name)}${size}</div>${mods}${note}`
    })
    .join('<hr>')
  const body = `
    <h1>Pedido #${o.number}</h1>
    <p class="c b">${esc(o.table_label || CHANNEL_LABEL[o.channel])}${stationName ? ` · ${esc(stationName)}` : ''}</p>
    <p class="c s">${esc(fmtTime(o.received_at ?? o.created_at))} · objetivo ${o.target_minutes} min</p>
    <hr>${items}
    ${o.note ? `<hr><p class="b">“${esc(o.note)}”</p>` : ''}`
  printHtml(`Comanda #${o.number}`, body)
}
