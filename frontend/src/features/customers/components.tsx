import { useState } from 'react'

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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { useAuth } from '@/lib/auth'
import { fmtMoney, PAYMENT_LABEL } from '@/lib/format'
import { cn } from '@/lib/utils'
import { useDepsChanged } from '@/hooks/use-deps-changed'

import { useAdjustPoints, useRegisterPayment, useSaveCustomer } from './api'
import type { Customer } from './types'

const AVATAR_TONES = [
  'bg-primary/15 text-primary',
  'bg-success/15 text-success',
  'bg-info/15 text-info',
  'bg-warning/25 text-warning-foreground dark:text-warning',
  'bg-destructive/10 text-destructive',
]

function initials(name: string) {
  const parts = name.replace(/\(.*?\)/g, '').trim().split(/\s+/).filter(Boolean)
  return ((parts[0]?.[0] ?? '?') + (parts.length > 1 ? parts[parts.length - 1][0] : '')).toUpperCase()
}

export function CustomerAvatar({ id, name, className }: { id: number; name: string; className?: string }) {
  return (
    <div
      className={cn(
        'flex size-9 shrink-0 items-center justify-center rounded-full text-sm font-semibold',
        AVATAR_TONES[id % AVATAR_TONES.length],
        className,
      )}
      aria-hidden
    >
      {initials(name)}
    </div>
  )
}

/** Create / edit dialog. Pass `customer` to edit. */
export function CustomerFormDialog({
  open,
  onOpenChange,
  customer,
  onSaved,
}: {
  open: boolean
  onOpenChange: (o: boolean) => void
  customer?: Customer | null
  onSaved?: (c: Customer) => void
}) {
  const { can } = useAuth()
  const save = useSaveCustomer()
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')
  const [email, setEmail] = useState('')
  const [birthday, setBirthday] = useState('')
  const [notes, setNotes] = useState('')
  const [limit, setLimit] = useState<number | null>(0)

  if (useDepsChanged([open, customer]) && open) {
    setName(customer?.name ?? '')
    setPhone(customer?.phone ?? '')
    setEmail(customer?.email ?? '')
    setBirthday(customer?.birthday ?? '')
    setNotes(customer?.notes ?? '')
    setLimit(customer?.credit_limit_cents ?? 0)
  }

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return
    const data = {
      name: name.trim(),
      phone: phone.trim() || null,
      email: email.trim() || null,
      birthday: birthday || null,
      notes: notes.trim() || null,
      ...(can('encargado') ? { credit_limit_cents: limit ?? 0 } : {}),
    }
    save.mutate(
      { id: customer?.id, data },
      {
        onSuccess: (c) => {
          onOpenChange(false)
          onSaved?.(c)
        },
      },
    )
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <form onSubmit={submit} className="grid gap-4">
          <DialogHeader>
            <DialogTitle>{customer ? 'Editar cliente' : 'Nuevo cliente'}</DialogTitle>
            <DialogDescription>
              Guardá sus datos y preferencias para atenderlo mejor la próxima vez.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-2">
            <Label htmlFor="c-name">Nombre</Label>
            <Input id="c-name" value={name} onChange={(e) => setName(e.target.value)} autoFocus required />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="grid gap-2">
              <Label htmlFor="c-phone">Teléfono</Label>
              <Input id="c-phone" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="11 5555-0000" />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="c-email">Email</Label>
              <Input id="c-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="c-bday">Cumpleaños</Label>
              <Input id="c-bday" type="date" value={birthday} onChange={(e) => setBirthday(e.target.value)} />
            </div>
            {can('encargado') && (
              <div className="grid gap-2">
                <Label htmlFor="c-limit">Límite cuenta corriente</Label>
                <MoneyInput id="c-limit" value={limit} onChange={setLimit} />
              </div>
            )}
          </div>
          <div className="grid gap-2">
            <Label htmlFor="c-notes">Preferencias / notas</Label>
            <Textarea
              id="c-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Ej.: latte con leche de avena, sin azúcar"
              rows={3}
            />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancelar
            </Button>
            <Button type="submit" disabled={save.isPending || !name.trim()}>
              {save.isPending ? 'Guardando…' : 'Guardar'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

const PAY_METHODS = ['efectivo', 'transferencia', 'debito', 'credito', 'qr']

export function PaymentDialog({
  open,
  onOpenChange,
  customer,
}: {
  open: boolean
  onOpenChange: (o: boolean) => void
  customer: Customer
}) {
  const pay = useRegisterPayment(customer.id)
  const [amount, setAmount] = useState<number | null>(null)
  const [method, setMethod] = useState('efectivo')

  if (useDepsChanged([open, customer.balance_cents]) && open) {
    setAmount(customer.balance_cents)
    setMethod('efectivo')
  }

  const tooMuch = amount != null && amount > customer.balance_cents
  const valid = amount != null && amount > 0 && !tooMuch

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!valid) return
    pay.mutate({ amount_cents: amount!, method }, { onSuccess: () => onOpenChange(false) })
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <form onSubmit={submit} className="grid gap-4">
          <DialogHeader>
            <DialogTitle>Registrar pago</DialogTitle>
            <DialogDescription>
              {customer.name} debe <span className="tabular font-medium text-foreground">{fmtMoney(customer.balance_cents)}</span>
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-2">
            <Label htmlFor="p-amount">Monto</Label>
            <MoneyInput id="p-amount" value={amount} onChange={setAmount} autoFocus />
            {tooMuch && <p className="text-xs text-destructive">No puede superar la deuda.</p>}
            <div className="flex gap-2">
              <Button type="button" size="sm" variant="secondary" onClick={() => setAmount(customer.balance_cents)}>
                Total
              </Button>
              <Button
                type="button"
                size="sm"
                variant="secondary"
                onClick={() => setAmount(Math.round(customer.balance_cents / 2))}
              >
                Mitad
              </Button>
            </div>
          </div>
          <div className="grid gap-2">
            <Label>Medio de pago</Label>
            <Select value={method} onValueChange={setMethod}>
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {PAY_METHODS.map((m) => (
                  <SelectItem key={m} value={m}>
                    {PAYMENT_LABEL[m] ?? m}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {method === 'efectivo' && (
              <p className="text-xs text-muted-foreground">Se registra como ingreso en la caja abierta.</p>
            )}
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancelar
            </Button>
            <Button type="submit" disabled={!valid || pay.isPending}>
              {pay.isPending ? 'Registrando…' : 'Registrar pago'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export function PointsDialog({
  open,
  onOpenChange,
  customer,
}: {
  open: boolean
  onOpenChange: (o: boolean) => void
  customer: Customer
}) {
  const adjust = useAdjustPoints(customer.id)
  const [points, setPoints] = useState('')
  const [reason, setReason] = useState('')

  if (useDepsChanged([open]) && open) {
    setPoints('')
    setReason('')
  }

  const n = Number.parseInt(points, 10)
  const valid = Number.isFinite(n) && n !== 0 && reason.trim() && customer.points + n >= 0

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!valid) return
    adjust.mutate({ points: n, reason: reason.trim() }, { onSuccess: () => onOpenChange(false) })
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <form onSubmit={submit} className="grid gap-4">
          <DialogHeader>
            <DialogTitle>Ajustar puntos</DialogTitle>
            <DialogDescription>
              Saldo actual: <span className="tabular font-medium text-foreground">{customer.points} pts</span>. Usá un
              número negativo para descontar.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-2">
            <Label htmlFor="pt-n">Puntos</Label>
            <Input
              id="pt-n"
              inputMode="numeric"
              value={points}
              onChange={(e) => setPoints(e.target.value.replace(/[^\d-]/g, ''))}
              placeholder="Ej.: 20 o -10"
              className="tabular"
              autoFocus
            />
            {Number.isFinite(n) && n !== 0 && (
              <p className={cn('text-xs', customer.points + n < 0 ? 'text-destructive' : 'text-muted-foreground')}>
                Quedaría en {customer.points + n} pts
              </p>
            )}
          </div>
          <div className="grid gap-2">
            <Label htmlFor="pt-r">Motivo</Label>
            <Input id="pt-r" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Ej.: compensación por demora" />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancelar
            </Button>
            <Button type="submit" disabled={!valid || adjust.isPending}>
              Guardar ajuste
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
