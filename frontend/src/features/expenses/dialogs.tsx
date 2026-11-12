import { Camera, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'

import { MoneyInput } from '@/components/money-input'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { useCurrentCash } from '@/features/cash/api'
import { usePaymentMethods } from '@/features/sales/api'
import { useDepsChanged } from '@/hooks/use-deps-changed'
import { fmtMoney, isoDate } from '@/lib/format'

import { fetchReceiptUrl, useExpenseCategories, usePayExpense, useReceipt, useSaveCategory, useSaveExpense, useSaveRecurring } from './api'
import type { Expense, ExpenseKind, ExpenseStatus, RecurringExpense } from './types'
import { KIND_LABEL } from './utils'

const CASH = 'efectivo'
/** Methods that make sense to pay an expense with (not "cuenta corriente" or the cafe's own MP charges). */
function useExpenseMethods() {
  const methods = usePaymentMethods()
  return (methods.data ?? []).filter((m) => m.code !== 'cuenta_corriente' && !m.code.startsWith('mp_'))
}

function MethodSelect({ value, onChange, id }: { value: string; onChange: (v: string) => void; id?: string }) {
  const methods = useExpenseMethods()
  return (
    <Select value={value || 'none'} onValueChange={(v) => onChange(v === 'none' ? '' : v)}>
      <SelectTrigger id={id} className="w-full">
        <SelectValue placeholder="Sin indicar" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="none">Sin indicar</SelectItem>
        {methods.map((m) => (
          <SelectItem key={m.code} value={m.code}>
            {m.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

function CategorySelect({ value, onChange, id }: { value: number | null; onChange: (id: number, kind: ExpenseKind) => void; id?: string }) {
  const cats = useExpenseCategories()
  const active = (cats.data ?? []).filter((c) => c.active || c.id === value)
  return (
    <Select
      value={value ? String(value) : ''}
      onValueChange={(v) => {
        const c = active.find((x) => x.id === Number(v))
        if (c) onChange(c.id, c.kind)
      }}
    >
      <SelectTrigger id={id} className="w-full">
        <SelectValue placeholder="Elegí una categoría" />
      </SelectTrigger>
      <SelectContent>
        {active.map((c) => (
          <SelectItem key={c.id} value={String(c.id)}>
            {c.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

/** "Lo pagué con plata de la caja": only for cash and with an open drawer. */
function FromCashSwitch({ method, value, onChange }: { method: string; value: boolean; onChange: (v: boolean) => void }) {
  const cash = useCurrentCash()
  if (method !== CASH) return null
  const open = !!cash.data
  return (
    <label className="flex items-start justify-between gap-3 rounded-xl border p-3 text-sm">
      <span>
        <span className="font-medium">Sale de la caja</span>
        <span className="block text-xs text-muted-foreground">
          {open ? 'Se registra un egreso en la caja abierta (baja el efectivo esperado).' : 'No hay una caja abierta.'}
        </span>
      </span>
      <Switch checked={value && open} disabled={!open} onCheckedChange={onChange} aria-label="Sale de la caja" />
    </label>
  )
}

// ------------------------------------------------------------------ new / edit expense
export function ExpenseDialog({
  open,
  expense,
  onOpenChange,
}: {
  open: boolean
  expense: Expense | null
  onOpenChange: (o: boolean) => void
}) {
  const save = useSaveExpense()
  const [categoryId, setCategoryId] = useState<number | null>(null)
  const [kind, setKind] = useState<ExpenseKind>('variable')
  const [description, setDescription] = useState('')
  const [amount, setAmount] = useState<number | null>(null)
  const [date, setDate] = useState(isoDate())
  const [status, setStatus] = useState<ExpenseStatus>('paid')
  const [due, setDue] = useState('')
  const [method, setMethod] = useState('')
  const [fromCash, setFromCash] = useState(false)
  const [notes, setNotes] = useState('')

  if (useDepsChanged([open, expense]) && open) {
    setCategoryId(expense?.category_id ?? null)
    setKind(expense?.kind ?? 'variable')
    setDescription(expense?.description ?? '')
    setAmount(expense?.amount_cents ?? null)
    setDate(expense?.date ?? isoDate())
    setStatus(expense?.status ?? 'paid')
    setDue(expense?.due_date ?? '')
    setMethod(expense?.payment_method ?? '')
    setFromCash(false)
    setNotes(expense?.notes ?? '')
  }

  const valid = !!categoryId && description.trim().length > 0 && !!amount && amount > 0
  const editing = !!expense

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{editing ? 'Editar gasto' : 'Nuevo gasto'}</DialogTitle>
          <DialogDescription>
            Alquiler, servicios, sueldos, impuestos… Las compras de mercadería no van acá: entran por el costo de lo vendido.
          </DialogDescription>
        </DialogHeader>
        <form
          className="grid gap-4"
          onSubmit={(e) => {
            e.preventDefault()
            if (!valid) return
            const body = {
              category_id: categoryId!,
              kind,
              description: description.trim(),
              amount_cents: amount!,
              date,
              due_date: status === 'pending' ? due || date : null,
              payment_method: method || null,
              notes: notes.trim() || null,
              ...(editing
                ? {}
                : {
                    status,
                    from_cash: status === 'paid' && method === CASH && fromCash,
                  }),
            }
            save.mutate({ id: expense?.id, body }, { onSuccess: () => onOpenChange(false) })
          }}
        >
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="grid gap-1.5">
              <Label htmlFor="exp-cat">Categoría</Label>
              <CategorySelect
                id="exp-cat"
                value={categoryId}
                onChange={(id, k) => {
                  setCategoryId(id)
                  if (!editing) setKind(k)
                }}
              />
            </div>
            <div className="grid gap-1.5">
              <Label>Tipo</Label>
              <ToggleGroup
                type="single"
                variant="outline"
                value={kind}
                onValueChange={(v) => v && setKind(v as ExpenseKind)}
                className="w-full"
              >
                <ToggleGroupItem value="fixed" className="flex-1">
                  Fijo
                </ToggleGroupItem>
                <ToggleGroupItem value="variable" className="flex-1">
                  Variable
                </ToggleGroupItem>
              </ToggleGroup>
            </div>
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="exp-desc">Concepto</Label>
            <Input
              id="exp-desc"
              maxLength={200}
              placeholder="Ej.: Luz de octubre"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="grid gap-1.5">
              <Label htmlFor="exp-amount">Monto</Label>
              <MoneyInput id="exp-amount" value={amount} onChange={setAmount} />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="exp-date">Fecha (mes al que corresponde)</Label>
              <Input id="exp-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
            </div>
          </div>
          {!editing && (
            <ToggleGroup
              type="single"
              variant="outline"
              value={status}
              onValueChange={(v) => v && setStatus(v as ExpenseStatus)}
              className="w-full"
            >
              <ToggleGroupItem value="paid" className="flex-1">
                Ya lo pagué
              </ToggleGroupItem>
              <ToggleGroupItem value="pending" className="flex-1">
                Pendiente de pago
              </ToggleGroupItem>
            </ToggleGroup>
          )}
          <div className="grid gap-4 sm:grid-cols-2">
            {(status === 'pending' || (editing && expense?.status === 'pending')) && (
              <div className="grid gap-1.5">
                <Label htmlFor="exp-due">Vence el</Label>
                <Input id="exp-due" type="date" value={due} onChange={(e) => setDue(e.target.value)} />
              </div>
            )}
            <div className="grid gap-1.5">
              <Label htmlFor="exp-method">Medio de pago</Label>
              <MethodSelect id="exp-method" value={method} onChange={setMethod} />
            </div>
          </div>
          {!editing && status === 'paid' && <FromCashSwitch method={method} value={fromCash} onChange={setFromCash} />}
          {editing && expense?.from_cash && (
            <p className="text-xs text-muted-foreground">
              Salió de la caja: si cambiás el monto o el medio de pago, se corrige el egreso (solo con esa caja abierta).
            </p>
          )}
          <div className="grid gap-1.5">
            <Label htmlFor="exp-notes">Notas (opcional)</Label>
            <Textarea id="exp-notes" rows={2} maxLength={1000} value={notes} onChange={(e) => setNotes(e.target.value)} />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancelar
            </Button>
            <Button type="submit" disabled={!valid || save.isPending}>
              {editing ? 'Guardar' : 'Cargar gasto'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// ------------------------------------------------------------------ pay a pending expense
export function PayDialog({ expense, onOpenChange }: { expense: Expense | null; onOpenChange: (o: boolean) => void }) {
  const pay = usePayExpense()
  const [amount, setAmount] = useState<number | null>(null)
  const [method, setMethod] = useState('')
  const [fromCash, setFromCash] = useState(false)
  if (useDepsChanged([expense]) && expense) {
    setAmount(expense.amount_cents)
    setMethod(expense.payment_method ?? '')
    setFromCash(false)
  }
  if (!expense) return null
  return (
    <Dialog open={!!expense} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Marcar como pagado</DialogTitle>
          <DialogDescription>
            {expense.description} · {expense.category_name}
          </DialogDescription>
        </DialogHeader>
        <form
          className="grid gap-4"
          onSubmit={(e) => {
            e.preventDefault()
            if (!amount) return
            pay.mutate(
              {
                id: expense.id,
                body: {
                  amount_cents: amount,
                  payment_method: method || null,
                  from_cash: method === CASH && fromCash,
                },
              },
              { onSuccess: () => onOpenChange(false) },
            )
          }}
        >
          <div className="grid gap-1.5">
            <Label htmlFor="pay-amount">Monto pagado</Label>
            <MoneyInput id="pay-amount" value={amount} onChange={setAmount} />
            <p className="text-xs text-muted-foreground">Si la factura vino distinta (luz, gas), corregí el monto acá.</p>
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="pay-method">Medio de pago</Label>
            <MethodSelect id="pay-method" value={method} onChange={setMethod} />
          </div>
          <FromCashSwitch method={method} value={fromCash} onChange={setFromCash} />
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancelar
            </Button>
            <Button type="submit" disabled={!amount || pay.isPending}>
              Pagar {amount ? fmtMoney(amount) : ''}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// ------------------------------------------------------------------ receipt photo
export function ReceiptDialog({ expense, onOpenChange }: { expense: Expense | null; onOpenChange: (o: boolean) => void }) {
  const receipt = useReceipt()
  const [img, setImg] = useState<{ key: string; url: string } | null>(null)
  const id = expense?.id
  const has = expense?.has_receipt
  // A new upload changes `updated` (the list refetches), so the photo is fetched again.
  const key = `${id}:${has}:${expense?.paid_at ?? ''}:${receipt.submittedAt}`
  useEffect(() => {
    if (!id || !has) return
    let alive = true
    let made: string | null = null
    fetchReceiptUrl(id)
      .then((u) => {
        made = u
        if (alive) setImg({ key, url: u })
      })
      .catch(() => undefined)
    return () => {
      alive = false
      if (made) URL.revokeObjectURL(made)
    }
  }, [id, has, key])
  const url = has && img?.key === key ? img.url : null
  if (!expense) return null
  return (
    <Dialog open={!!expense} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Comprobante</DialogTitle>
          <DialogDescription>
            {expense.description} · {fmtMoney(expense.amount_cents)}
          </DialogDescription>
        </DialogHeader>
        {expense.has_receipt && url ? (
          <img src={url} alt={`Comprobante de ${expense.description}`} className="max-h-[60vh] w-full rounded-xl border object-contain" />
        ) : (
          <p className="rounded-xl border border-dashed p-6 text-center text-sm text-muted-foreground">
            Sacale una foto a la factura o al ticket para tenerlo a mano (JPG, PNG o WebP, hasta 8 MB).
          </p>
        )}
        <DialogFooter className="gap-2">
          {expense.has_receipt && (
            <Button
              type="button"
              variant="outline"
              onClick={() => receipt.mutate({ id: expense.id, file: null })}
              disabled={receipt.isPending}
            >
              <Trash2 /> Quitar
            </Button>
          )}
          <Button asChild>
            <label className="cursor-pointer">
              <Camera /> {expense.has_receipt ? 'Cambiar foto' : 'Subir foto'}
              <input
                type="file"
                accept="image/jpeg,image/png,image/webp"
                capture="environment"
                className="sr-only"
                onChange={(e) => {
                  const f = e.target.files?.[0]
                  if (f) receipt.mutate({ id: expense.id, file: f })
                  e.target.value = ''
                }}
              />
            </label>
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ------------------------------------------------------------------ monthly fixed expense
export function RecurringDialog({
  open,
  item,
  onOpenChange,
}: {
  open: boolean
  item: RecurringExpense | null
  onOpenChange: (o: boolean) => void
}) {
  const save = useSaveRecurring()
  const [categoryId, setCategoryId] = useState<number | null>(null)
  const [description, setDescription] = useState('')
  const [amount, setAmount] = useState<number | null>(null)
  const [day, setDay] = useState('10')
  const [method, setMethod] = useState('')
  const [notes, setNotes] = useState('')
  if (useDepsChanged([open, item]) && open) {
    setCategoryId(item?.category_id ?? null)
    setDescription(item?.description ?? '')
    setAmount(item?.amount_cents ?? null)
    setDay(String(item?.day_of_month ?? 10))
    setMethod(item?.payment_method ?? '')
    setNotes(item?.notes ?? '')
  }
  const d = Number(day)
  const valid = !!categoryId && description.trim() && !!amount && d >= 1 && d <= 31
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{item ? 'Editar gasto fijo' : 'Nuevo gasto fijo mensual'}</DialogTitle>
          <DialogDescription>
            Cada mes se genera solo como pendiente, con su vencimiento, y aparece en Avisos unos días antes.
          </DialogDescription>
        </DialogHeader>
        <form
          className="grid gap-4"
          onSubmit={(e) => {
            e.preventDefault()
            if (!valid) return
            save.mutate(
              {
                id: item?.id,
                body: {
                  category_id: categoryId!,
                  description: description.trim(),
                  amount_cents: amount!,
                  day_of_month: d,
                  payment_method: method || null,
                  notes: notes.trim() || null,
                },
              },
              { onSuccess: () => onOpenChange(false) },
            )
          }}
        >
          <div className="grid gap-1.5">
            <Label htmlFor="rec-cat">Categoría</Label>
            <CategorySelect id="rec-cat" value={categoryId} onChange={(id) => setCategoryId(id)} />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="rec-desc">Concepto</Label>
            <Input
              id="rec-desc"
              maxLength={200}
              placeholder="Ej.: Alquiler del local"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="grid gap-1.5">
              <Label htmlFor="rec-amount">Monto estimado</Label>
              <MoneyInput id="rec-amount" value={amount} onChange={setAmount} />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="rec-day">Vence el día</Label>
              <Input id="rec-day" inputMode="numeric" value={day} onChange={(e) => setDay(e.target.value.replace(/\D/g, '').slice(0, 2))} />
            </div>
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="rec-method">Medio de pago habitual</Label>
            <MethodSelect id="rec-method" value={method} onChange={setMethod} />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="rec-notes">Notas (opcional)</Label>
            <Input id="rec-notes" maxLength={1000} value={notes} onChange={(e) => setNotes(e.target.value)} />
          </div>
          {item && <p className="text-xs text-muted-foreground">Los cambios valen para los próximos meses; los ya generados no cambian.</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancelar
            </Button>
            <Button type="submit" disabled={!valid || save.isPending}>
              Guardar
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// ------------------------------------------------------------------ categories
export function CategoriesDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const cats = useExpenseCategories()
  const save = useSaveCategory()
  const [name, setName] = useState('')
  const [kind, setKind] = useState<ExpenseKind>('variable')
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Categorías de gastos</DialogTitle>
          <DialogDescription>Renombralas, archivá las que no uses o sumá las tuyas.</DialogDescription>
        </DialogHeader>
        <ul className="max-h-[50vh] divide-y overflow-y-auto rounded-xl border">
          {(cats.data ?? []).map((c) => (
            <li key={c.id} className="flex items-center gap-2 px-3 py-2">
              <Input
                defaultValue={c.name}
                aria-label={`Nombre de ${c.name}`}
                className="h-8 flex-1"
                disabled={!c.active}
                onBlur={(e) => {
                  const v = e.target.value.trim()
                  if (v && v !== c.name) save.mutate({ id: c.id, body: { name: v } })
                }}
              />
              <Badge variant="outline">{KIND_LABEL[c.kind]}</Badge>
              <Button type="button" size="sm" variant="ghost" onClick={() => save.mutate({ id: c.id, body: { active: !c.active } })}>
                {c.active ? 'Archivar' : 'Reactivar'}
              </Button>
            </li>
          ))}
        </ul>
        <form
          className="flex flex-wrap items-end gap-2"
          onSubmit={(e) => {
            e.preventDefault()
            if (!name.trim()) return
            save.mutate({ body: { name: name.trim(), kind } }, { onSuccess: () => setName('') })
          }}
        >
          <div className="grid flex-1 gap-1.5">
            <Label htmlFor="cat-new">Nueva categoría</Label>
            <Input id="cat-new" maxLength={60} placeholder="Ej.: Seguros" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <ToggleGroup type="single" variant="outline" value={kind} onValueChange={(v) => v && setKind(v as ExpenseKind)}>
            <ToggleGroupItem value="fixed">Fijo</ToggleGroupItem>
            <ToggleGroupItem value="variable">Variable</ToggleGroupItem>
          </ToggleGroup>
          <Button type="submit" disabled={!name.trim() || save.isPending}>
            Agregar
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  )
}
