import { ArrowDownCircle, ArrowUpCircle, Lock, Unlock } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { MoneyInput } from '@/components/money-input'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { fmtMoney } from '@/lib/format'
import { cn } from '@/lib/utils'

import { useCashMovement, useCloseCash, useOpenCash } from './api'
import type { CashSession, CashSessionDetail } from './types'

export function OpenCashDialog({
  open,
  onOpenChange,
  onOpened,
}: {
  open: boolean
  onOpenChange: (o: boolean) => void
  onOpened?: () => void
}) {
  const [amount, setAmount] = useState<number | null>(null)
  const m = useOpenCash()
  const submit = () =>
    m.mutate(amount ?? 0, {
      onSuccess: () => {
        toast.success('Caja abierta. ¡Buen turno!')
        setAmount(null)
        onOpenChange(false)
        onOpened?.()
      },
      onError: (e) => toast.error(e.message),
    })
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Unlock className="size-5 text-primary" /> Abrir caja
          </DialogTitle>
          <DialogDescription>Ingresá el fondo de cambio con el que arrancás el turno.</DialogDescription>
        </DialogHeader>
        <div className="space-y-2">
          <Label htmlFor="opening">Fondo inicial en efectivo</Label>
          <MoneyInput
            id="opening"
            value={amount}
            onChange={setAmount}
            autoFocus
            placeholder="0"
            className="[&_input]:h-12 [&_input]:text-lg"
            onKeyDown={(e) => e.key === 'Enter' && submit()}
          />
          <div className="flex flex-wrap gap-2 pt-1">
            {[1000000, 2000000, 3000000, 5000000].map((v) => (
              <Button key={v} variant="outline" size="sm" onClick={() => setAmount(v)}>
                {fmtMoney(v, { short: true })}
              </Button>
            ))}
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" size="lg" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button size="lg" onClick={submit} disabled={m.isPending}>
            Abrir caja
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export function MovementDialog({
  type,
  onOpenChange,
}: {
  type: 'in' | 'out' | null
  onOpenChange: (o: boolean) => void
}) {
  const [amount, setAmount] = useState<number | null>(null)
  const [reason, setReason] = useState('')
  const m = useCashMovement()
  const isIn = type === 'in'
  const suggestions = isIn
    ? ['Ingreso de cambio', 'Reposición de fondo', 'Cobro de cuenta corriente']
    : ['Pago a proveedor', 'Retiro de efectivo', 'Compra de insumos menores', 'Propinas']
  const submit = () => {
    if (!type || !amount || amount <= 0) return toast.error('Ingresá un monto válido')
    if (!reason.trim()) return toast.error('Indicá el motivo')
    m.mutate(
      { type, amount_cents: amount, reason: reason.trim() },
      {
        onSuccess: () => {
          toast.success(isIn ? 'Ingreso registrado' : 'Egreso registrado')
          setAmount(null)
          setReason('')
          onOpenChange(false)
        },
        onError: (e) => toast.error(e.message),
      },
    )
  }
  return (
    <Dialog open={type != null} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {isIn ? (
              <ArrowDownCircle className="size-5 text-success" />
            ) : (
              <ArrowUpCircle className="size-5 text-destructive" />
            )}
            {isIn ? 'Ingreso de efectivo' : 'Egreso de efectivo'}
          </DialogTitle>
          <DialogDescription>Queda registrado en el arqueo del efectivo.</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-2">
            <Label htmlFor="mv-amount">Monto</Label>
            <MoneyInput id="mv-amount" value={amount} onChange={setAmount} autoFocus className="[&_input]:h-11" />
          </div>
          <div className="space-y-2">
            <Label htmlFor="mv-reason">Motivo</Label>
            <Input
              id="mv-reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="h-11"
              placeholder="Ej.: pago a proveedor de lácteos"
              onKeyDown={(e) => e.key === 'Enter' && submit()}
            />
            <div className="flex flex-wrap gap-1.5">
              {suggestions.map((s) => (
                <Button key={s} variant="secondary" size="sm" onClick={() => setReason(s)}>
                  {s}
                </Button>
              ))}
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" size="lg" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button size="lg" onClick={submit} disabled={m.isPending}>
            Registrar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export function DiffText({ cents, className }: { cents: number | null; className?: string }) {
  if (cents == null) return <span className={cn('text-muted-foreground', className)}>—</span>
  return (
    <span
      className={cn(
        'tabular font-medium',
        cents === 0 ? 'text-success' : cents > 0 ? 'text-info' : 'text-destructive',
        className,
      )}
    >
      {cents > 0 ? '+' : ''}
      {fmtMoney(cents)}
    </span>
  )
}

export function CloseCashDialog({
  session,
  open,
  onOpenChange,
  onClosed,
}: {
  session: CashSession
  open: boolean
  onOpenChange: (o: boolean) => void
  onClosed?: (s: CashSessionDetail) => void
}) {
  const [counted, setCounted] = useState<Record<string, number | null>>({})
  const [notes, setNotes] = useState('')
  const m = useCloseCash()

  const value = (method: string, expected: number) =>
    method in counted ? counted[method] : method === 'efectivo' ? null : expected
  const rows = session.by_method.map((r) => {
    const c = value(r.method, r.expected_cents)
    return { ...r, counted: c, diff: c == null ? null : c - r.expected_cents }
  })
  const totalDiff = rows.reduce((a, r) => a + (r.diff ?? 0), 0)
  const missingCash = rows.some((r) => r.method === 'efectivo' && r.counted == null)

  const submit = () => {
    if (missingCash) return toast.error('Contá el efectivo antes de cerrar')
    m.mutate(
      {
        counts: rows.map((r) => ({ payment_method: r.method, counted_cents: r.counted ?? 0 })),
        notes: notes.trim() || undefined,
      },
      {
        onSuccess: (s) => {
          toast.success('Caja cerrada')
          setCounted({})
          setNotes('')
          onOpenChange(false)
          onClosed?.(s)
        },
        onError: (e) => toast.error(e.message),
      },
    )
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Lock className="size-5 text-primary" /> Cerrar caja · arqueo
          </DialogTitle>
          <DialogDescription>
            Contá lo que hay en cada medio. El efectivo esperado incluye el fondo inicial, los ingresos y los egresos.
          </DialogDescription>
        </DialogHeader>
        <div className="overflow-hidden rounded-xl border">
          <div className="grid grid-cols-[1.3fr_1fr_1.3fr_1fr] gap-3 bg-muted/50 px-4 py-2 text-xs font-medium text-muted-foreground">
            <span>Medio</span>
            <span className="text-right">Esperado</span>
            <span>Contado</span>
            <span className="text-right">Diferencia</span>
          </div>
          {rows.map((r) => (
            <div key={r.method} className="grid grid-cols-[1.3fr_1fr_1.3fr_1fr] items-center gap-3 border-t px-4 py-2.5">
              <div>
                <p className="font-medium">{r.name}</p>
                <p className="text-xs text-muted-foreground">{r.count} ventas</p>
              </div>
              <span className="tabular text-right">{fmtMoney(r.expected_cents)}</span>
              <MoneyInput
                value={r.counted}
                onChange={(v) => setCounted((c) => ({ ...c, [r.method]: v }))}
                placeholder={r.method === 'efectivo' ? 'Contá…' : undefined}
                aria-label={`Contado ${r.name}`}
                autoFocus={r.method === 'efectivo'}
                className="[&_input]:h-10"
              />
              <DiffText cents={r.diff} className="text-right" />
            </div>
          ))}
          <div className="flex items-center justify-between border-t bg-muted/30 px-4 py-3">
            <span className="font-medium">Diferencia total</span>
            <DiffText cents={missingCash ? null : totalDiff} className="text-lg" />
          </div>
        </div>
        {session.courtesy_count > 0 && (
          <p className="rounded-xl bg-primary/10 px-4 py-2.5 text-sm" data-testid="close-courtesy">
            <span className="font-medium">
              Cortesías: {session.courtesy_count} ({fmtMoney(session.courtesy_cents)} a precio de carta, costo{' '}
              {fmtMoney(session.courtesy_cost_cents)})
            </span>
            <span className="text-muted-foreground"> · no se cobraron, no suman al esperado.</span>
          </p>
        )}
        <div className="space-y-2">
          <Label htmlFor="close-notes">Observaciones</Label>
          <Textarea id="close-notes" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Opcional" rows={2} />
        </div>
        <DialogFooter>
          <Button variant="outline" size="lg" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button size="lg" onClick={submit} disabled={m.isPending || missingCash}>
            Cerrar caja
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
