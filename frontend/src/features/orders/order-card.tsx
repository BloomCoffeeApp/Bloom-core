import {
  Banknote,
  Bike,
  Check,
  ChefHat,
  CircleX,
  Clock,
  Globe,
  HandPlatter,
  type LucideIcon,
  MapPin,
  MessageCircle,
  MoreVertical,
  Phone,
  QrCode,
  Receipt,
  RefreshCw,
  Undo2,
  UserRoundCheck,
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { fmtMoney, fmtNumber } from '@/lib/format'
import { cn } from '@/lib/utils'

import { CHANNEL_LABEL } from '../sales/types'
import { fmtClock } from './timing'
import type { Level, Order, OrderAction } from './types'

const LEVEL_STYLE: Record<Level, { card: string; clock: string; label: string }> = {
  ok: { card: 'border-success/50', clock: 'bg-success/15 text-success', label: 'A tiempo' },
  warn: { card: 'border-warning', clock: 'bg-warning/25 text-foreground', label: 'Por vencer' },
  late: { card: 'border-destructive ring-2 ring-destructive/30', clock: 'bg-destructive text-white', label: 'Atrasado' },
  pending: { card: 'border-info border-dashed', clock: 'bg-info/15 text-info', label: 'Esperando confirmación' },
}

const ICONS: Record<string, LucideIcon> = {
  check: Check,
  chef: ChefHat,
  x: CircleX,
  undo: Undo2,
  hand: HandPlatter,
  bike: Bike,
  banknote: Banknote,
}

const TONE: Record<OrderAction['tone'], { variant: 'default' | 'outline' | 'secondary'; className?: string }> = {
  primary: { variant: 'default', className: 'flex-1' },
  success: { variant: 'default', className: 'flex-1 bg-success text-white hover:bg-success/90' },
  secondary: { variant: 'secondary', className: 'flex-1' },
  outline: { variant: 'outline', className: 'px-4' },
  danger: { variant: 'outline', className: 'px-4 text-destructive' },
}

const PAY_LABEL = { online: 'Pago online', transfer: 'Transferencia', cash: 'Efectivo' } as const

export interface CardActions {
  /** Runs one action of the order's flow (the page opens a dialog when the action needs input). */
  onAction: (o: Order, a: OrderAction) => void
  onWhatsApp?: (o: Order) => void
  onOnline?: (o: Order, action: 'check-payment' | 'register-sale' | 'update-customer') => void
  busy?: boolean
}

function ActionIcon({ name }: { name: string | null }) {
  const Icon = name ? ICONS[name] : undefined
  return Icon ? <Icon /> : null
}

function where(o: Order) {
  if (o.online) return CHANNEL_LABEL[o.channel]
  if (o.table_label) return o.source === 'table' || /^mesa/i.test(o.table_label) ? o.table_label : `Mesa ${o.table_label}`
  return CHANNEL_LABEL[o.channel]
}

function OnlineBlock({ o, actions }: { o: Order; actions: CardActions }) {
  const on = o.online!
  const payChip =
    o.payment_status === 'paid'
      ? { text: 'Pagado', cls: 'bg-success/15 text-success' }
      : o.payment_status === 'refunded'
        ? { text: 'Devuelto', cls: 'bg-muted text-muted-foreground' }
        : o.payment_status === 'refund_due'
          ? { text: 'Devolver el pago a mano', cls: 'bg-destructive/15 text-destructive' }
          : { text: on.payment_method === 'cash' ? 'Cobrar al entregar' : 'Sin pagar', cls: 'bg-warning/25 text-foreground' }
  return (
    <div className="space-y-1.5 rounded-xl bg-muted/50 p-2.5 text-sm" data-testid="online-info">
      <p className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <span className="font-semibold text-foreground">{on.customer_name}</span>
        {on.customer_phone && (
          <span className="inline-flex items-center gap-1 text-muted-foreground">
            <Phone className="size-3.5" /> {on.customer_phone}
          </span>
        )}
      </p>
      {on.address && (
        <p className="flex items-start gap-1">
          <MapPin className="mt-0.5 size-3.5 shrink-0" />
          <span>
            {on.address}
            {on.address_ref && <span className="text-muted-foreground"> · {on.address_ref}</span>}
            {on.delivery_zone && <span className="text-muted-foreground"> · {on.delivery_zone}</span>}
          </span>
        </p>
      )}
      <p className="flex flex-wrap items-center gap-1.5">
        <span className="font-semibold tabular-nums">{fmtMoney(on.total_cents)}</span>
        {on.payment_method && <span className="text-muted-foreground">· {PAY_LABEL[on.payment_method]}</span>}
        <span className={cn('rounded-full px-2 text-xs font-medium', payChip.cls)}>{payChip.text}</span>
        {on.eta_minutes != null && <span className="text-muted-foreground">· {on.eta_minutes} min</span>}
        {on.expires_in_s != null && o.status === 'awaiting_pay' && (
          <span className="text-muted-foreground">· vence en {Math.ceil(on.expires_in_s / 60)} min</span>
        )}
      </p>
      {on.invoice_request && (
        <p className="rounded-lg border border-info/60 bg-info/10 p-2 text-xs" data-testid="invoice-request">
          <b>Pidió factura</b>: {[on.invoice_request.name, on.invoice_request.cuit && `CUIT ${on.invoice_request.cuit}`, on.invoice_request.email].filter(Boolean).join(' · ') || 'sin datos'}
        </p>
      )}
      {on.customer_changes.length > 0 && (
        <div className="rounded-lg border border-warning/60 bg-warning/10 p-2" data-testid="customer-changes">
          <p className="font-medium">Datos nuevos del cliente</p>
          <ul className="text-xs">
            {on.customer_changes.map((c) => (
              <li key={c.field}>
                {c.label}: <span className="line-through opacity-70">{c.saved || '—'}</span> → <b>{c.new}</b>
              </li>
            ))}
          </ul>
          {actions.onOnline && (
            <Button variant="outline" className="mt-1.5 h-11 w-full" disabled={actions.busy} onClick={() => actions.onOnline!(o, 'update-customer')}>
              <UserRoundCheck /> Actualizar datos del cliente
            </Button>
          )}
        </div>
      )}
      <div className="flex flex-wrap gap-1.5 pt-0.5">
        {actions.onWhatsApp && on.customer_phone && (
          <Button variant="outline" className="h-11" onClick={() => actions.onWhatsApp!(o)} aria-label={`WhatsApp a ${on.customer_name ?? 'el cliente'}`}>
            <MessageCircle /> WhatsApp
          </Button>
        )}
        {actions.onOnline && o.status === 'awaiting_pay' && on.payment_method === 'online' && (
          <Button variant="outline" className="h-11" disabled={actions.busy} onClick={() => actions.onOnline!(o, 'check-payment')}>
            <RefreshCw /> Ver si pagó
          </Button>
        )}
        {actions.onOnline && o.payment_status === 'paid' && !on.sale_registered && (
          <Button variant="outline" className="h-11" disabled={actions.busy} onClick={() => actions.onOnline!(o, 'register-sale')}>
            <Receipt /> Registrar venta
          </Button>
        )}
      </div>
    </div>
  )
}

export function OrderCard({ order: o, elapsed, level, actions }: { order: Order; elapsed: number; level: Level; actions: CardActions }) {
  const st = LEVEL_STYLE[level]
  const ready = o.status === 'ready' || o.status === 'dispatched'
  const waiting = o.received_at == null
  const main = o.actions.filter((a) => a.place === 'main')
  const menu = o.actions.filter((a) => a.place === 'menu')
  return (
    <article
      data-testid="order-card"
      data-order={o.number}
      data-status={o.status}
      data-flow={o.flow}
      data-level={level}
      aria-label={`Pedido ${o.number}`}
      className={cn('flex flex-col gap-3 rounded-2xl border-2 bg-card p-3 shadow-xs', ready ? 'border-success/40 opacity-95' : st.card)}
    >
      <header className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="font-heading text-3xl leading-none font-semibold tabular-nums">#{o.number}</p>
          <p className="mt-1 flex flex-wrap items-center gap-1.5 text-sm text-muted-foreground">
            {o.source === 'table' && <QrCode className="size-3.5" aria-label="Pedido desde la mesa" />}
            {o.source === 'online' && <Globe className="size-3.5" aria-label="Pedido online" />}
            <span className="font-medium text-foreground">{where(o)}</span>
            {o.table_label && !o.online && <span>· {CHANNEL_LABEL[o.channel]}</span>}
            {o.sale_number && <span>· Ticket #{o.sale_number}</span>}
          </p>
          <span className="mt-1.5 inline-block rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary" data-testid="order-status">
            {o.status_label}
          </span>
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
          <span className="text-xs text-muted-foreground">{waiting ? 'sin confirmar' : `objetivo ${o.target_minutes} min`}</span>
        </div>
      </header>

      {o.online && <OnlineBlock o={o} actions={actions} />}

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

      {(main.length > 0 || menu.length > 0) && (
        <footer className="mt-auto flex gap-2">
          {main.map((a) => {
            const t = TONE[a.tone]
            return (
              <Button
                key={`${a.to}-${a.label}`}
                variant={t.variant}
                className={cn('h-12 text-base', t.className)}
                disabled={actions.busy}
                onClick={() => actions.onAction(o, a)}
              >
                <ActionIcon name={a.icon} /> {a.label}
              </Button>
            )
          })}
          {menu.length > 0 && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" className="size-12" aria-label={`Más opciones del pedido ${o.number}`}>
                  <MoreVertical />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                {menu.map((a, i) => (
                  <div key={`${a.to}-${a.label}`}>
                    {a.tone === 'danger' && i > 0 && <DropdownMenuSeparator />}
                    <DropdownMenuItem variant={a.tone === 'danger' ? 'destructive' : 'default'} onSelect={() => actions.onAction(o, a)}>
                      <ActionIcon name={a.icon} /> {a.label}
                    </DropdownMenuItem>
                  </div>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        </footer>
      )}
    </article>
  )
}
