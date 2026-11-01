import { Check, ChefHat, CircleX, Clock, HandPlatter, MoreVertical, QrCode, Undo2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { fmtNumber } from '@/lib/format'
import { cn } from '@/lib/utils'

import { CHANNEL_LABEL } from '../sales/types'
import type { Level, Order, OrderStatus } from './types'
import { fmtClock } from './timing'

const LEVEL_STYLE: Record<Level, { card: string; clock: string; label: string }> = {
  ok: { card: 'border-success/50', clock: 'bg-success/15 text-success', label: 'A tiempo' },
  warn: { card: 'border-warning', clock: 'bg-warning/25 text-foreground', label: 'Por vencer' },
  late: { card: 'border-destructive ring-2 ring-destructive/30', clock: 'bg-destructive text-white', label: 'Atrasado' },
  pending: { card: 'border-info border-dashed', clock: 'bg-info/15 text-info', label: 'Esperando confirmación' },
}

export interface CardActions {
  onStatus: (o: Order, status: OrderStatus) => void
  onCancel: (o: Order) => void
  busy?: boolean
}

export function OrderCard({ order: o, elapsed, level, actions }: { order: Order; elapsed: number; level: Level; actions: CardActions }) {
  const st = LEVEL_STYLE[level]
  const ready = o.status === 'ready'
  return (
    <article
      data-testid="order-card"
      data-order={o.number}
      data-status={o.status}
      data-level={level}
      aria-label={`Pedido ${o.number}`}
      className={cn('flex flex-col gap-3 rounded-2xl border-2 bg-card p-3 shadow-xs', ready ? 'border-success/40 opacity-95' : st.card)}
    >
      <header className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="font-heading text-3xl leading-none font-semibold tabular-nums">#{o.number}</p>
          <p className="mt-1 flex flex-wrap items-center gap-1.5 text-sm text-muted-foreground">
            {o.source === 'table' && <QrCode className="size-3.5" aria-label="Pedido desde la mesa" />}
            <span className="font-medium text-foreground">
              {o.table_label ? (o.source === 'table' || /^mesa/i.test(o.table_label) ? o.table_label : `Mesa ${o.table_label}`) : CHANNEL_LABEL[o.channel]}
            </span>
            {o.table_label && <span>· {CHANNEL_LABEL[o.channel]}</span>}
            {o.sale_number && <span>· Ticket #{o.sale_number}</span>}
          </p>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1">
          <span
            className={cn('flex items-center gap-1 rounded-xl px-2.5 py-1 font-heading text-xl font-semibold tabular-nums', ready ? 'bg-muted text-muted-foreground' : st.clock)}
            aria-label={`${ready ? 'Preparado en' : 'Tiempo'} ${fmtClock(elapsed)}${ready ? '' : ` · ${st.label}`}`}
            data-testid="order-timer"
          >
            <Clock className="size-4" />
            {fmtClock(elapsed)}
          </span>
          <span className="text-xs text-muted-foreground">
            {o.status === 'pending' ? 'sin confirmar' : `objetivo ${o.target_minutes} min`}
          </span>
        </div>
      </header>

      <ul className="space-y-1.5">
        {o.items.map((it) => (
          <li key={it.id} className="leading-snug">
            <span className="text-lg font-semibold">
              <span className="tabular-nums">{fmtNumber(it.qty, 1)}×</span> {it.name}
            </span>
            {it.size_name && <span className="ml-1.5 rounded-md bg-primary/10 px-1.5 py-0.5 text-sm font-medium text-primary">{it.size_name}</span>}
            {it.modifiers.length > 0 && <p className="text-sm text-muted-foreground">{it.modifiers.join(' · ')}</p>}
            {it.notes && <p className="text-sm font-medium text-primary italic">» {it.notes}</p>}
          </li>
        ))}
      </ul>
      {o.note && <p className="rounded-lg bg-muted px-2.5 py-1.5 text-sm italic">“{o.note}”</p>}
      {o.prepared_by_name && o.status !== 'received' && (
        <p className="text-xs text-muted-foreground">
          <ChefHat className="mr-1 inline size-3.5" />
          {o.prepared_by_name}
        </p>
      )}

      <footer className="mt-auto flex gap-2">
        {o.status === 'pending' && (
          <>
            <Button className="h-12 flex-1 text-base" disabled={actions.busy} onClick={() => actions.onStatus(o, 'received')}>
              <Check /> Confirmar
            </Button>
            <Button variant="outline" className="h-12 px-4 text-base" disabled={actions.busy} onClick={() => actions.onCancel(o)}>
              <CircleX /> Rechazar
            </Button>
          </>
        )}
        {o.status === 'received' && (
          <>
            <Button className="h-12 flex-1 text-base" disabled={actions.busy} onClick={() => actions.onStatus(o, 'preparing')}>
              <ChefHat /> Empezar
            </Button>
            <Button variant="outline" className="h-12 px-4 text-base" disabled={actions.busy} onClick={() => actions.onStatus(o, 'ready')}>
              <Check /> Listo
            </Button>
          </>
        )}
        {o.status === 'preparing' && (
          <Button className="h-12 flex-1 bg-success text-base text-white hover:bg-success/90" disabled={actions.busy} onClick={() => actions.onStatus(o, 'ready')}>
            <Check /> Listo
          </Button>
        )}
        {o.status === 'ready' && (
          <Button variant="secondary" className="h-12 flex-1 text-base" disabled={actions.busy} onClick={() => actions.onStatus(o, 'delivered')}>
            <HandPlatter /> Entregado
          </Button>
        )}
        {o.status !== 'pending' && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" className="size-12" aria-label={`Más opciones del pedido ${o.number}`}>
                <MoreVertical />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {o.status === 'preparing' && (
                <DropdownMenuItem onSelect={() => actions.onStatus(o, 'received')}>
                  <Undo2 /> Volver a «Nuevo»
                </DropdownMenuItem>
              )}
              {o.status === 'ready' && (
                <DropdownMenuItem onSelect={() => actions.onStatus(o, 'preparing')}>
                  <Undo2 /> Volver a «En preparación»
                </DropdownMenuItem>
              )}
              {o.status !== 'ready' && (
                <>
                  {o.status === 'preparing' && <DropdownMenuSeparator />}
                  <DropdownMenuItem variant="destructive" onSelect={() => actions.onCancel(o)}>
                    <CircleX /> Cancelar pedido
                  </DropdownMenuItem>
                </>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </footer>
    </article>
  )
}
