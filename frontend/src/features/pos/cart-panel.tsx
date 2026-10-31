import {
  BadgePercent,
  Bike,
  Coffee,
  Gift,
  Minus,
  Plus,
  ShoppingBag,
  Star,
  StickyNote,
  Trash2,
  UserRound,
  UtensilsCrossed,
  X,
} from 'lucide-react'
import { useState } from 'react'

import { EmptyState } from '@/components/empty-state'
import { MoneyInput } from '@/components/money-input'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { fmtMoney } from '@/lib/format'
import { cn } from '@/lib/utils'

import type { Channel } from '../sales/types'
import { CustomerPicker } from './customer-picker'
import type { CartLine, PosConfig } from './types'
import type { CartApi, CartTotals } from './use-cart'

const CHANNELS: { id: Channel; label: string; icon: typeof Coffee }[] = [
  { id: 'salon', label: 'Salón', icon: UtensilsCrossed },
  { id: 'llevar', label: 'Para llevar', icon: ShoppingBag },
  { id: 'delivery', label: 'Delivery', icon: Bike },
]

function LineDialog({
  line,
  canDiscount,
  onOpenChange,
  onSave,
}: {
  line: CartLine | null
  canDiscount: boolean
  onOpenChange: (o: boolean) => void
  onSave: (patch: { notes: string; discount_cents: number; qty: number }) => void
}) {
  return (
    <Dialog open={line != null} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        {line && <LineForm key={line.key} line={line} canDiscount={canDiscount} onSave={onSave} onCancel={() => onOpenChange(false)} />}
      </DialogContent>
    </Dialog>
  )
}

function LineForm({
  line,
  canDiscount,
  onSave,
  onCancel,
}: {
  line: CartLine
  canDiscount: boolean
  onSave: (patch: { notes: string; discount_cents: number; qty: number }) => void
  onCancel: () => void
}) {
  const [notes, setNotes] = useState(line.notes)
  const [disc, setDisc] = useState<number | null>(line.discount_cents || null)
  const [qty, setQty] = useState(line.qty)
  const gross = line.unit_cents * qty
  return (
    <>
      <DialogHeader>
        <DialogTitle>{line.name}</DialogTitle>
        <DialogDescription>
          {fmtMoney(line.unit_cents)} c/u{line.modifiers.length ? ` · ${line.modifiers.map((m) => m.name).join(', ')}` : ''}
        </DialogDescription>
      </DialogHeader>
      <div className="space-y-4">
        <div className="flex items-center justify-center gap-4">
          <Button variant="outline" className="size-12" onClick={() => setQty((q) => Math.max(1, q - 1))} aria-label="Restar">
            <Minus />
          </Button>
          <span className="tabular w-10 text-center text-2xl font-semibold">{qty}</span>
          <Button variant="outline" className="size-12" onClick={() => setQty((q) => q + 1)} aria-label="Sumar">
            <Plus />
          </Button>
        </div>
        <div className="space-y-2">
          <Label htmlFor="line-notes">Nota</Label>
          <Textarea id="line-notes" rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Ej.: sin azúcar, para compartir…" />
        </div>
        {canDiscount && (
          <div className="space-y-2">
            <Label htmlFor="line-disc">Descuento en este ítem</Label>
            <MoneyInput id="line-disc" value={disc} onChange={setDisc} className="[&_input]:h-11" />
            <div className="flex gap-2">
              {[10, 20, 50, 100].map((p) => (
                <Button key={p} variant="secondary" size="sm" onClick={() => setDisc(Math.round((gross * p) / 100))}>
                  {p === 100 ? 'Invita la casa' : `${p}%`}
                </Button>
              ))}
            </div>
          </div>
        )}
      </div>
      <DialogFooter>
        <Button variant="outline" className="h-11" onClick={onCancel}>
          Cancelar
        </Button>
        <Button className="h-11 px-6" onClick={() => onSave({ notes, discount_cents: Math.min(disc ?? 0, gross), qty })}>
          Guardar
        </Button>
      </DialogFooter>
    </>
  )
}

function DiscountDialog({
  open,
  onOpenChange,
  value,
  subtotal,
  onSave,
}: {
  open: boolean
  onOpenChange: (o: boolean) => void
  value: { mode: 'amount' | 'pct'; value: number }
  subtotal: number
  onSave: (v: { mode: 'amount' | 'pct'; value: number }) => void
}) {
  const [mode, setMode] = useState(value.mode)
  const [amount, setAmount] = useState<number | null>(value.mode === 'amount' ? value.value || null : null)
  const [pct, setPct] = useState(value.mode === 'pct' ? String(value.value || '') : '')
  const preview = mode === 'pct' ? Math.round((subtotal * (Number(pct) || 0)) / 100) : amount ?? 0
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle>Descuento a la venta</DialogTitle>
          <DialogDescription>Se aplica sobre el subtotal de {fmtMoney(subtotal)}.</DialogDescription>
        </DialogHeader>
        <div className="grid grid-cols-2 gap-1 rounded-xl bg-muted p-1">
          {(['pct', 'amount'] as const).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={cn('h-10 rounded-lg text-sm font-medium', mode === m ? 'bg-background shadow-sm' : 'text-muted-foreground')}
            >
              {m === 'pct' ? 'Porcentaje' : 'Monto fijo'}
            </button>
          ))}
        </div>
        {mode === 'pct' ? (
          <div className="space-y-2">
            <div className="relative">
              <Input inputMode="decimal" className="h-12 pr-8 text-lg" value={pct} onChange={(e) => setPct(e.target.value.replace(/[^\d.,]/g, '').replace(',', '.'))} autoFocus />
              <span className="absolute top-1/2 right-3 -translate-y-1/2 text-muted-foreground">%</span>
            </div>
            <div className="flex gap-2">
              {[5, 10, 15, 20].map((p) => (
                <Button key={p} variant="secondary" className="flex-1" onClick={() => setPct(String(p))}>
                  {p}%
                </Button>
              ))}
            </div>
          </div>
        ) : (
          <MoneyInput value={amount} onChange={setAmount} autoFocus className="[&_input]:h-12 [&_input]:text-lg" />
        )}
        <p className="text-sm text-muted-foreground">
          Descuento: <span className="tabular font-medium text-foreground">{fmtMoney(Math.min(preview, subtotal))}</span>
        </p>
        <DialogFooter>
          <Button
            variant="outline"
            className="h-11"
            onClick={() => {
              onSave({ mode: 'amount', value: 0 })
              onOpenChange(false)
            }}
          >
            Quitar
          </Button>
          <Button
            className="h-11 px-6"
            onClick={() => {
              onSave(mode === 'pct' ? { mode, value: Math.min(Number(pct) || 0, 100) } : { mode, value: amount ?? 0 })
              onOpenChange(false)
            }}
          >
            Aplicar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export function CartPanel({
  cartApi,
  totals,
  config,
  cashOpen,
  onCheckout,
}: {
  cartApi: CartApi
  totals: CartTotals
  config: PosConfig | undefined
  cashOpen: boolean
  onCheckout: () => void
}) {
  const { cart } = cartApi
  const [editing, setEditing] = useState<CartLine | null>(null)
  const [discOpen, setDiscOpen] = useState(false)
  const [custOpen, setCustOpen] = useState(false)
  const canDiscount = !!config?.can_discount
  const loyalty = config?.loyalty
  const ppr = loyalty?.enabled ? loyalty.points_per_reward : 0
  const maxRedeem = cart.customer && ppr > 0 ? Math.floor(cart.customer.points / ppr) * ppr : 0

  return (
    <div className="flex min-h-0 flex-col border-t bg-card md:border-t-0 md:border-l">
      {/* Channel + table */}
      <div className="space-y-3 border-b p-3">
        <div className="grid grid-cols-3 gap-1 rounded-xl bg-muted p-1">
          {CHANNELS.map((c) => (
            <button
              key={c.id}
              onClick={() => cartApi.setChannel(c.id)}
              className={cn(
                'flex h-11 items-center justify-center gap-1.5 rounded-lg text-sm font-medium transition-colors',
                cart.channel === c.id ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground',
              )}
            >
              <c.icon className="size-4" /> {c.label}
            </button>
          ))}
        </div>
        <div className="flex gap-2">
          {cart.channel === 'salon' && (
            <Input
              value={cart.table_label}
              onChange={(e) => cartApi.setTable(e.target.value.slice(0, 20))}
              placeholder="Mesa"
              className="h-11 w-24"
              aria-label="Mesa"
            />
          )}
          {cart.customer ? (
            <div className="flex h-11 min-w-0 flex-1 items-center gap-2 rounded-lg border bg-primary/5 px-3">
              <UserRound className="size-4 shrink-0 text-primary" />
              <button className="min-w-0 flex-1 truncate text-left text-sm font-medium" onClick={() => setCustOpen(true)}>
                {cart.customer.name}
              </button>
              <span className="flex shrink-0 items-center gap-1 text-xs text-muted-foreground">
                <Star className="size-3 text-warning" />
                {cart.customer.points}
              </span>
              <button onClick={() => cartApi.setCustomer(null)} className="text-muted-foreground hover:text-foreground" aria-label="Quitar cliente">
                <X className="size-4" />
              </button>
            </div>
          ) : (
            <Button variant="outline" className="h-11 flex-1 justify-start" onClick={() => setCustOpen(true)}>
              <UserRound /> Cliente (opcional)
            </Button>
          )}
        </div>
        {cart.customer && maxRedeem > 0 && loyalty && (
          <div className="flex items-center gap-2 rounded-xl bg-warning/15 px-3 py-2 text-sm">
            <Gift className="size-4 shrink-0" />
            <span className="flex-1">
              {cart.points_to_redeem
                ? `Canjea ${cart.points_to_redeem} pts (−${fmtMoney((cart.points_to_redeem / ppr) * loyalty.reward_value_cents, { short: true })})`
                : `Puede canjear ${ppr} pts por ${fmtMoney(loyalty.reward_value_cents, { short: true })}`}
            </span>
            {cart.points_to_redeem > 0 && (
              <Button size="sm" variant="ghost" onClick={() => cartApi.setPoints(cart.points_to_redeem - ppr)}>
                <Minus />
              </Button>
            )}
            {cart.points_to_redeem < maxRedeem && (
              <Button size="sm" variant="secondary" onClick={() => cartApi.setPoints(cart.points_to_redeem + ppr)}>
                Canjear
              </Button>
            )}
          </div>
        )}
      </div>

      {/* Lines */}
      <div className="min-h-0 flex-1 overflow-y-auto">
        {cart.lines.length === 0 ? (
          <div className="p-4">
            <EmptyState icon={Coffee} title="Carrito vacío" description="Tocá un producto para empezar la venta." />
          </div>
        ) : (
          <ul className="divide-y">
            {cart.lines.map((l) => (
              <li key={l.key} className="flex items-start gap-2 px-3 py-2.5">
                <button className="min-w-0 flex-1 text-left" onClick={() => setEditing(l)}>
                  <p className="leading-tight font-medium">{l.name}</p>
                  {l.modifiers.length > 0 && <p className="text-xs text-muted-foreground">{l.modifiers.map((m) => m.name).join(' · ')}</p>}
                  {l.notes && (
                    <p className="flex items-center gap-1 text-xs text-muted-foreground italic">
                      <StickyNote className="size-3" /> {l.notes}
                    </p>
                  )}
                  <p className="tabular mt-0.5 text-xs text-muted-foreground">
                    {fmtMoney(l.unit_cents)} c/u
                    {l.discount_cents > 0 && <span className="text-success"> · −{fmtMoney(l.discount_cents)}</span>}
                  </p>
                </button>
                <div className="flex shrink-0 flex-col items-end gap-1.5">
                  <span className="tabular font-semibold">{fmtMoney(l.unit_cents * l.qty - l.discount_cents)}</span>
                  <div className="flex items-center gap-1">
                    <Button
                      variant="outline"
                      size="icon-lg"
                      className="size-10"
                      onClick={() => cartApi.setQty(l.key, l.qty - 1)}
                      aria-label={l.qty === 1 ? 'Quitar' : 'Restar'}
                    >
                      {l.qty === 1 ? <Trash2 className="text-destructive" /> : <Minus />}
                    </Button>
                    <span className="tabular w-7 text-center font-semibold">{l.qty}</span>
                    <Button variant="outline" size="icon-lg" className="size-10" onClick={() => cartApi.setQty(l.key, l.qty + 1)} aria-label="Sumar">
                      <Plus />
                    </Button>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Totals */}
      <div className="space-y-2 border-t p-3">
        <div className="space-y-1 text-sm">
          <div className="flex justify-between text-muted-foreground">
            <span>
              Subtotal · {totals.items} {totals.items === 1 ? 'ítem' : 'ítems'}
            </span>
            <span className="tabular">{fmtMoney(totals.subtotal)}</span>
          </div>
          {totals.discount > 0 && (
            <div className="flex justify-between text-success">
              <span>Descuento{cart.discount.mode === 'pct' ? ` ${cart.discount.value}%` : ''}</span>
              <span className="tabular">−{fmtMoney(totals.discount)}</span>
            </div>
          )}
          {totals.pointsDiscount > 0 && (
            <div className="flex justify-between text-success">
              <span>Canje de puntos</span>
              <span className="tabular">−{fmtMoney(totals.pointsDiscount)}</span>
            </div>
          )}
        </div>
        <div className="flex items-end justify-between">
          <div className="flex gap-1">
            {canDiscount && (
              <Button variant="ghost" size="sm" onClick={() => setDiscOpen(true)} disabled={!cart.lines.length}>
                <BadgePercent /> Descuento
              </Button>
            )}
            {cart.lines.length > 0 && (
              <Button variant="ghost" size="sm" className="text-muted-foreground" onClick={cartApi.clear}>
                <Trash2 /> Vaciar
              </Button>
            )}
          </div>
          <div className="text-right">
            <p className="text-xs text-muted-foreground">Total</p>
            <p className="tabular font-heading text-4xl leading-none font-semibold tracking-tight">{fmtMoney(totals.total)}</p>
          </div>
        </div>
        {totals.pointsEarned > 0 && <p className="text-right text-xs text-muted-foreground">Suma {totals.pointsEarned} puntos</p>}
        <Button
          className="h-16 w-full rounded-2xl text-xl font-bold tracking-wide shadow-md"
          disabled={!cart.lines.length || !cashOpen}
          onClick={onCheckout}
        >
          COBRAR <span className="ml-2 text-sm font-normal opacity-70">F9</span>
        </Button>
      </div>

      <LineDialog
        line={editing}
        canDiscount={canDiscount}
        onOpenChange={(o) => !o && setEditing(null)}
        onSave={(patch) => {
          if (editing) cartApi.updateLine(editing.key, patch)
          setEditing(null)
        }}
      />
      {discOpen && (
        <DiscountDialog open={discOpen} onOpenChange={setDiscOpen} value={cart.discount} subtotal={totals.subtotal} onSave={cartApi.setDiscount} />
      )}
      <CustomerPicker open={custOpen} onOpenChange={setCustOpen} onPick={cartApi.setCustomer} />
    </div>
  )
}
