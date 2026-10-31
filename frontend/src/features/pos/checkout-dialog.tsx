import {
  ArrowLeftRight,
  Banknote,
  BookUser,
  CreditCard,
  Gift,
  Landmark,
  QrCode,
  Split,
  Trash2,
  Wallet,
  type LucideIcon,
} from 'lucide-react'
import { useEffect, useState } from 'react'

import { MoneyInput } from '@/components/money-input'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import { fmtMoney } from '@/lib/format'
import { cn } from '@/lib/utils'

import type { PaymentIn, PaymentMethod } from '../sales/types'
import type { PosCustomer } from './types'

const ICONS: Record<string, LucideIcon> = {
  efectivo: Banknote,
  debito: CreditCard,
  credito: CreditCard,
  transferencia: Landmark,
  qr: QrCode,
  cuenta_corriente: BookUser,
}

const BILLS = [100000, 200000, 1000000, 2000000]

/** Courtesy ("invita la casa"): registered with its stock movements but $0 charged. */
export interface CourtesyIn {
  reason: string
}

export type CheckoutConfirm = (payments: PaymentIn[], courtesy: CourtesyIn | null) => void

function CourtesyToggle({ on, onChange }: { on: boolean; onChange: (on: boolean) => void }) {
  return (
    <label
      className={cn(
        'flex min-h-14 cursor-pointer items-center gap-3 rounded-2xl border px-4 py-2 transition-colors',
        on ? 'border-primary bg-primary/10' : 'bg-card hover:bg-muted',
      )}
    >
      <Gift className={cn('size-6 shrink-0', on ? 'text-primary' : 'text-muted-foreground')} />
      <span className="min-w-0 flex-1 leading-tight">
        <span className="block font-medium">Cortesía (no se cobra)</span>
        <span className="block text-xs text-muted-foreground">Invita la casa: descuenta stock pero no suma plata a la caja.</span>
      </span>
      <Switch checked={on} onCheckedChange={onChange} aria-label="Cortesía (no se cobra)" />
    </label>
  )
}

function CourtesyBody({
  listTotal,
  total,
  submitting,
  onConfirm,
}: {
  listTotal: number
  total: number
  submitting: boolean
  onConfirm: CheckoutConfirm
}) {
  const [reason, setReason] = useState('')
  const confirm = () => {
    if (!submitting) onConfirm([], { reason: reason.trim() })
  }

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Enter' && !(e.target instanceof HTMLTextAreaElement)) {
        e.preventDefault()
        confirm()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  return (
    <div className="grid gap-5 md:grid-cols-[1fr_1.1fr]">
      <div className="rounded-2xl bg-primary/10 p-4 text-center" data-testid="courtesy-total">
        <p className="text-sm text-muted-foreground">Total a cobrar</p>
        <p className="tabular font-heading text-5xl font-semibold tracking-tight">{fmtMoney(0)}</p>
        <p className="tabular mt-1 text-lg text-muted-foreground line-through">{fmtMoney(listTotal)}</p>
        <p className="mt-1 text-xs text-muted-foreground">Valor a precio de carta</p>
      </div>
      <div className="flex flex-col gap-4">
        <div className="space-y-2">
          <label htmlFor="courtesy-reason" className="text-sm font-medium">
            Para quién / motivo <span className="font-normal text-muted-foreground">(opcional)</span>
          </label>
          <Input
            id="courtesy-reason"
            value={reason}
            maxLength={200}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Ej.: cliente habitual, proveedor, compensación…"
            className="h-12 text-base"
          />
          {listTotal !== total && (
            <p className="text-xs text-muted-foreground">En una cortesía no se aplican descuentos ni canjes de puntos.</p>
          )}
          <p className="text-xs text-muted-foreground">Queda registrada a tu nombre y no suma puntos ni cuenta corriente.</p>
        </div>
        <Button className="mt-auto h-16 text-xl font-semibold" disabled={submitting} onClick={confirm}>
          <Gift className="size-6" /> {submitting ? 'Registrando…' : 'Registrar cortesía'}
        </Button>
      </div>
    </div>
  )
}

interface PayRow {
  method: string
  amount: number
  tendered: number | null
}

function CheckoutBody({
  total,
  methods,
  customer,
  submitting,
  onConfirm,
}: {
  total: number
  methods: PaymentMethod[]
  customer: PosCustomer | null
  submitting: boolean
  onConfirm: CheckoutConfirm
}) {
  const [split, setSplit] = useState(false)
  const [rows, setRows] = useState<PayRow[]>(() => (total > 0 ? [{ method: 'efectivo', amount: total, tendered: null }] : []))
  const [active, setActive] = useState(0)

  const paid = rows.reduce((a, r) => a + (r.amount || 0), 0)
  const remaining = total - paid
  const cashRow = rows[active]?.method === 'efectivo' ? rows[active] : rows.find((r) => r.method === 'efectivo')
  const change = cashRow && cashRow.tendered != null ? cashRow.tendered - cashRow.amount : null
  const shortCash = rows.some((r) => r.method === 'efectivo' && r.tendered != null && r.tendered < r.amount)
  const ccBlocked = rows.some((r) => r.method === 'cuenta_corriente') && !customer
  const ccOverLimit =
    customer && customer.credit_limit_cents > 0
      ? customer.balance_cents + rows.filter((r) => r.method === 'cuenta_corriente').reduce((a, r) => a + r.amount, 0) >
        customer.credit_limit_cents
      : false
  const canConfirm = remaining === 0 && !shortCash && !ccBlocked && !submitting

  const pickMethod = (code: string) => {
    if (!split) {
      setRows([{ method: code, amount: total, tendered: null }])
      setActive(0)
      return
    }
    const idx = rows.findIndex((r) => r.method === code)
    if (idx >= 0) {
      setActive(idx)
      return
    }
    setRows((r) => [...r, { method: code, amount: Math.max(remaining, 0), tendered: null }])
    setActive(rows.length)
  }

  const update = (i: number, patch: Partial<PayRow>) => setRows((r) => r.map((x, j) => (j === i ? { ...x, ...patch } : x)))
  const removeRow = (i: number) => {
    setRows((r) => r.filter((_, j) => j !== i))
    setActive(0)
  }

  const confirm = () => {
    if (!canConfirm) return
    onConfirm(
      rows
        .filter((r) => r.amount > 0)
        .map((r) => ({
          method: r.method,
          amount_cents: r.amount,
          tendered_cents: r.method === 'efectivo' && r.tendered != null ? r.tendered : null,
        })),
      null,
    )
  }

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Enter' && !(e.target instanceof HTMLTextAreaElement)) {
        e.preventDefault()
        confirm()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  const cashIdx = cashRow ? rows.indexOf(cashRow) : -1

  return (
    <div className="grid gap-5 md:grid-cols-[1fr_1.1fr]">
      <div className="space-y-4">
        <div className="rounded-2xl bg-primary/10 p-4 text-center">
          <p className="text-sm text-muted-foreground">Total a cobrar</p>
          <p className="tabular font-heading text-5xl font-semibold tracking-tight">{fmtMoney(total)}</p>
        </div>
        <div className="grid grid-cols-2 gap-2">
          {methods.map((m) => {
            const Icon = ICONS[m.code] ?? Wallet
            const on = rows.some((r) => r.method === m.code)
            const disabled = m.code === 'cuenta_corriente' && !customer
            return (
              <button
                key={m.code}
                onClick={() => pickMethod(m.code)}
                disabled={disabled || total === 0}
                title={disabled ? 'Elegí un cliente para cobrar a cuenta corriente' : undefined}
                className={cn(
                  'flex min-h-16 items-center gap-3 rounded-2xl border px-4 text-left font-medium transition-colors disabled:opacity-40',
                  on ? 'border-primary bg-primary text-primary-foreground' : 'bg-card hover:bg-muted',
                )}
              >
                <Icon className="size-6 shrink-0" />
                <span className="leading-tight">{m.name}</span>
              </button>
            )
          })}
        </div>
        <Button
          variant={split ? 'secondary' : 'outline'}
          className="h-12 w-full"
          onClick={() => {
            setSplit((s) => !s)
            if (split && rows.length > 1) {
              setRows([{ ...rows[active], amount: total, tendered: null }])
              setActive(0)
            }
          }}
          disabled={total === 0}
        >
          <Split /> {split ? 'Pago dividido activado' : 'Dividir pago'}
        </Button>
      </div>

      <div className="flex flex-col gap-4">
        <div className="space-y-2">
          {rows.length === 0 && total > 0 && <p className="text-sm text-muted-foreground">Elegí un medio de pago.</p>}
          {total === 0 && <p className="rounded-xl bg-success/15 p-3 text-sm">El total está cubierto con puntos. No hace falta cobrar.</p>}
          {rows.map((r, i) => {
            const m = methods.find((x) => x.code === r.method)
            const Icon = ICONS[r.method] ?? Wallet
            return (
              <div
                key={r.method}
                onClick={() => setActive(i)}
                className={cn('flex items-center gap-2 rounded-xl border p-2', i === active && 'border-primary ring-2 ring-primary/20')}
              >
                <Icon className="ml-1 size-5 shrink-0 text-muted-foreground" />
                <span className="min-w-0 flex-1 truncate font-medium">{m?.name ?? r.method}</span>
                <MoneyInput
                  value={r.amount}
                  onChange={(v) => update(i, { amount: v ?? 0 })}
                  disabled={!split}
                  aria-label={`Monto ${m?.name ?? r.method}`}
                  className="w-36 [&_input]:h-11 [&_input]:text-right [&_input]:text-base"
                />
                {split && (
                  <Button variant="ghost" size="icon-lg" onClick={() => removeRow(i)} aria-label="Quitar pago">
                    <Trash2 />
                  </Button>
                )}
              </div>
            )
          })}
          {split && remaining !== 0 && (
            <div className={cn('flex justify-between rounded-xl px-3 py-2 text-sm font-medium', remaining > 0 ? 'bg-warning/20' : 'bg-destructive/10 text-destructive')}>
              <span>{remaining > 0 ? 'Falta asignar' : 'Te pasaste por'}</span>
              <span className="tabular">{fmtMoney(Math.abs(remaining))}</span>
            </div>
          )}
          {ccBlocked && <p className="text-sm text-destructive">La cuenta corriente requiere un cliente.</p>}
          {ccOverLimit && <p className="text-sm text-destructive">Ojo: supera el límite de cuenta corriente del cliente.</p>}
        </div>

        {cashRow && cashIdx >= 0 && (
          <div className="space-y-3 rounded-2xl border p-3">
            <div className="flex items-center justify-between">
              <p className="font-medium">Efectivo recibido</p>
              <MoneyInput
                value={cashRow.tendered}
                onChange={(v) => update(cashIdx, { tendered: v })}
                placeholder="¿Con cuánto paga?"
                aria-label="Efectivo recibido"
                className="w-44 [&_input]:h-11 [&_input]:text-right [&_input]:text-base"
              />
            </div>
            <div className="grid grid-cols-5 gap-2">
              <Button variant="secondary" className="h-12" onClick={() => update(cashIdx, { tendered: cashRow.amount })}>
                Exacto
              </Button>
              {BILLS.map((b) => (
                <Button key={b} variant="outline" className="tabular h-12" onClick={() => update(cashIdx, { tendered: (cashRow.tendered ?? 0) + b })}>
                  +{fmtMoney(b, { short: true })}
                </Button>
              ))}
            </div>
            <div
              className={cn(
                'flex items-center justify-between rounded-xl px-4 py-3',
                change == null ? 'bg-muted/50' : change < 0 ? 'bg-destructive/10 text-destructive' : 'bg-success/15',
              )}
            >
              <span className="flex items-center gap-2 font-medium">
                <ArrowLeftRight className="size-4" /> {change != null && change < 0 ? 'Falta' : 'Vuelto'}
              </span>
              <span className="tabular font-heading text-4xl font-semibold">{change == null ? '—' : fmtMoney(Math.abs(change))}</span>
            </div>
            {cashRow.tendered != null && (
              <button className="text-xs text-muted-foreground underline" onClick={() => update(cashIdx, { tendered: null })}>
                Limpiar monto recibido
              </button>
            )}
          </div>
        )}

        <Button className="mt-auto h-16 text-xl font-semibold" disabled={!canConfirm} onClick={confirm}>
          {submitting ? 'Cobrando…' : `Confirmar cobro · ${fmtMoney(total)}`}
        </Button>
      </div>
    </div>
  )
}

function CheckoutContent({
  total,
  listTotal,
  methods,
  customer,
  submitting,
  onConfirm,
}: {
  total: number
  listTotal: number
  methods: PaymentMethod[]
  customer: PosCustomer | null
  submitting: boolean
  onConfirm: CheckoutConfirm
}) {
  const [courtesy, setCourtesy] = useState(false)
  return (
    <>
      <DialogHeader>
        <DialogTitle className="font-heading text-2xl">{courtesy ? 'Cortesía' : 'Cobrar'}</DialogTitle>
        <DialogDescription>
          {courtesy ? 'Invita la casa. Enter registra, Esc cancela.' : 'Elegí el medio de pago. Enter confirma, Esc cancela.'}
        </DialogDescription>
      </DialogHeader>
      <CourtesyToggle on={courtesy} onChange={setCourtesy} />
      {courtesy ? (
        <CourtesyBody listTotal={listTotal} total={total} submitting={submitting} onConfirm={onConfirm} />
      ) : (
        <CheckoutBody
          key={total}
          total={total}
          methods={methods}
          customer={customer}
          submitting={submitting}
          onConfirm={onConfirm}
        />
      )}
    </>
  )
}

export function CheckoutDialog({
  open,
  onOpenChange,
  total,
  listTotal,
  methods,
  customer,
  submitting,
  onConfirm,
}: {
  open: boolean
  onOpenChange: (o: boolean) => void
  total: number
  /** Menu value of the cart (no discounts/points): what a courtesy gives away. */
  listTotal: number
  methods: PaymentMethod[]
  customer: PosCustomer | null
  submitting: boolean
  onConfirm: CheckoutConfirm
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[95svh] overflow-y-auto sm:max-w-4xl">
        {/* Mounted only while open, so the courtesy toggle starts off on every checkout. */}
        {open && (
          <CheckoutContent
            total={total}
            listTotal={listTotal}
            methods={methods}
            customer={customer}
            submitting={submitting}
            onConfirm={onConfirm}
          />
        )}
      </DialogContent>
    </Dialog>
  )
}
