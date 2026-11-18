import { ArrowDownRight, ArrowUpRight, Check, ChevronsUpDown, History, PackageOpen } from 'lucide-react'
import { useMemo, useState } from 'react'

import { EmptyState } from '@/components/empty-state'
import { MoneyInput } from '@/components/money-input'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from '@/components/ui/command'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Skeleton } from '@/components/ui/skeleton'
import { Switch } from '@/components/ui/switch'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { useDepsChanged } from '@/hooks/use-deps-changed'
import { fmtDateTime, fmtNumber, fmtQty } from '@/lib/format'
import { cn } from '@/lib/utils'

import { useSuppliersLite } from './purchasing'
import {
  useAdjustStock,
  useMovements,
  useSaveStockCategory,
  useSaveStockItem,
  useStockCategories,
} from './api'
import { bulkCost, bulkFactor, bulkUnit, MOVEMENT_LABEL, STATUS_LABEL } from './stock-utils'
import type { StockItem, StockItemInput, StockStatus, Unit } from './types'

// ------------------------------------------------------------------ status visuals
export function StatusBadge({ status }: { status: StockStatus }) {
  const cls = {
    ok: 'bg-success/15 text-success',
    low: 'bg-warning/20 text-warning-foreground dark:text-warning',
    out: 'bg-destructive/10 text-destructive',
  }[status]
  return (
    <Badge variant="secondary" className={cn('gap-1.5', cls)}>
      <span
        className={cn(
          'size-1.5 rounded-full',
          status === 'ok' ? 'bg-success' : status === 'low' ? 'bg-warning' : 'bg-destructive',
        )}
      />
      {STATUS_LABEL[status]}
    </Badge>
  )
}

/** Level bar: fill relative to 2× the minimum, with a tick at the minimum. */
export function LevelBar({ item }: { item: Pick<StockItem, 'current_qty' | 'min_qty' | 'status'> }) {
  const scale = Math.max(item.min_qty * 2, item.current_qty, 1)
  const pct = Math.max(0, Math.min(100, (item.current_qty / scale) * 100))
  const minPct = item.min_qty > 0 ? (item.min_qty / scale) * 100 : null
  return (
    <div className="relative h-2 w-full min-w-24 overflow-hidden rounded-full bg-muted">
      <div
        className={cn(
          'h-full rounded-full transition-[width] motion-base',
          item.status === 'ok' ? 'bg-success' : item.status === 'low' ? 'bg-warning' : 'bg-destructive',
        )}
        style={{ width: `${pct}%` }}
      />
      {minPct != null && <div className="absolute inset-y-0 w-0.5 bg-foreground/40" style={{ left: `${minPct}%` }} />}
    </div>
  )
}

// ------------------------------------------------------------------ item picker
export function StockItemPicker({
  items,
  value,
  onChange,
  placeholder = 'Elegí un insumo…',
  excludeIds,
  className,
}: {
  items: StockItem[] | undefined
  value: number | null
  onChange: (item: StockItem) => void
  placeholder?: string
  excludeIds?: number[]
  className?: string
}) {
  const [open, setOpen] = useState(false)
  const selected = items?.find((i) => i.id === value)
  const grouped = useMemo(() => {
    const out = new Map<string, StockItem[]>()
    for (const i of items ?? []) {
      if (excludeIds?.includes(i.id) && i.id !== value) continue
      const k = i.category_name ?? 'Sin categoría'
      out.set(k, [...(out.get(k) ?? []), i])
    }
    return [...out.entries()].sort(([a], [b]) => a.localeCompare(b))
  }, [items, excludeIds, value])

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          className={cn('h-9 w-full justify-between font-normal', !selected && 'text-muted-foreground', className)}
        >
          <span className="truncate">{selected ? selected.name : placeholder}</span>
          <ChevronsUpDown className="opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-(--radix-popover-trigger-width) min-w-72 p-0" align="start">
        <Command>
          <CommandInput placeholder="Buscar insumo…" />
          <CommandList>
            <CommandEmpty>No hay insumos con ese nombre.</CommandEmpty>
            {grouped.map(([cat, list]) => (
              <CommandGroup key={cat} heading={cat}>
                {list.map((i) => (
                  <CommandItem
                    key={i.id}
                    value={`${i.name} ${i.id}`}
                    onSelect={() => {
                      onChange(i)
                      setOpen(false)
                    }}
                  >
                    <Check className={cn('size-4', value === i.id ? 'opacity-100' : 'opacity-0')} />
                    <span className="flex-1 truncate">{i.name}</span>
                    <span className="tabular text-xs text-muted-foreground">{fmtQty(i.current_qty, i.unit)}</span>
                  </CommandItem>
                ))}
              </CommandGroup>
            ))}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}

// ------------------------------------------------------------------ adjust / waste
export function AdjustDialog({ item, onOpenChange }: { item: StockItem | null; onOpenChange: (o: boolean) => void }) {
  const [mode, setMode] = useState<'set' | 'delta'>('set')
  const [qty, setQty] = useState('')
  const [reason, setReason] = useState('')
  const adjust = useAdjustStock()

  if (useDepsChanged([item]) && item) {
    setMode('set')
    setQty(String(item.current_qty))
    setReason('')
  }

  if (!item) return null
  const n = Number(qty.replace(',', '.'))
  const valid = qty.trim() !== '' && Number.isFinite(n) && reason.trim().length > 0
  const after = mode === 'set' ? n : item.current_qty + n
  const delta = mode === 'set' ? n - item.current_qty : n

  return (
    <Dialog open={!!item} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Ajustar stock</DialogTitle>
          <DialogDescription>
            {item.name} · hoy hay <span className="tabular font-medium text-foreground">{fmtQty(item.current_qty, item.unit)}</span>
          </DialogDescription>
        </DialogHeader>
        <form
          className="grid gap-4"
          onSubmit={(e) => {
            e.preventDefault()
            if (!valid) return
            adjust.mutate(
              mode === 'set'
                ? { stock_item_id: item.id, new_qty: n, reason: reason.trim() }
                : { stock_item_id: item.id, delta: n, reason: reason.trim() },
              { onSuccess: () => onOpenChange(false) },
            )
          }}
        >
          <ToggleGroup
            type="single"
            variant="outline"
            value={mode}
            onValueChange={(v) => {
              if (!v) return
              setMode(v as 'set' | 'delta')
              setQty(v === 'set' ? String(item.current_qty) : '')
            }}
            className="w-full"
          >
            <ToggleGroupItem value="set" className="flex-1">
              Cantidad real
            </ToggleGroupItem>
            <ToggleGroupItem value="delta" className="flex-1">
              Sumar / restar
            </ToggleGroupItem>
          </ToggleGroup>
          <div className="grid gap-1.5">
            <Label htmlFor="adj-qty">{mode === 'set' ? 'Cantidad que hay' : 'Diferencia (usá − para restar)'} ({item.unit})</Label>
            <Input id="adj-qty" inputMode="decimal" autoFocus className="tabular" value={qty} onChange={(e) => setQty(e.target.value)} />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="adj-reason">Motivo</Label>
            <Input id="adj-reason" placeholder="Ej.: error de carga, recuento…" value={reason} onChange={(e) => setReason(e.target.value)} />
          </div>
          {qty.trim() !== '' && Number.isFinite(n) && (
            <div className="flex items-center justify-between rounded-xl bg-muted/60 px-3 py-2 text-sm">
              <span className="text-muted-foreground">Queda en</span>
              <span className="tabular font-medium">
                {fmtQty(after, item.unit)}{' '}
                <span className={cn('text-xs', delta >= 0 ? 'text-success' : 'text-destructive')}>
                  ({delta >= 0 ? '+' : ''}
                  {fmtNumber(delta)} {item.unit})
                </span>
              </span>
            </div>
          )}
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

// ------------------------------------------------------------------ kardex
export function MovementsSheet({ item, onOpenChange }: { item: StockItem | null; onOpenChange: (o: boolean) => void }) {
  const { data, isLoading } = useMovements(item?.id ?? null)
  return (
    <Sheet open={!!item} onOpenChange={onOpenChange}>
      <SheetContent className="w-full gap-0 sm:max-w-lg">
        <SheetHeader className="border-b">
          <SheetTitle className="flex items-center gap-2 text-lg">
            <History className="size-5 text-primary" /> Movimientos
          </SheetTitle>
          <SheetDescription>
            {item?.name} · stock {item ? fmtQty(item.current_qty, item.unit) : ''}
          </SheetDescription>
        </SheetHeader>
        <ScrollArea className="min-h-0 flex-1">
          <div className="space-y-2 p-4">
            {isLoading &&
              Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-16 w-full rounded-xl" />)}
            {!isLoading && !data?.length && (
              <EmptyState icon={PackageOpen} title="Sin movimientos" description="Todavía no hubo entradas ni salidas." />
            )}
            {data?.map((m) => {
              const inbound = m.qty >= 0
              return (
                <div key={m.id} className="flex items-start gap-3 rounded-xl border bg-card p-3">
                  <div
                    className={cn(
                      'mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg',
                      inbound ? 'bg-success/15 text-success' : 'bg-destructive/10 text-destructive',
                    )}
                  >
                    {inbound ? <ArrowUpRight className="size-4" /> : <ArrowDownRight className="size-4" />}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium">{MOVEMENT_LABEL[m.type] ?? m.type}</span>
                      <span className={cn('tabular font-semibold', inbound ? 'text-success' : 'text-destructive')}>
                        {inbound ? '+' : ''}
                        {item ? fmtQty(m.qty, item.unit) : m.qty}
                      </span>
                    </div>
                    <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
                      <span className="truncate">
                        {fmtDateTime(m.ts)}
                        {m.user_name ? ` · ${m.user_name}` : ''}
                      </span>
                      <span className="tabular shrink-0">Saldo {item ? fmtQty(m.balance_after, item.unit) : m.balance_after}</span>
                    </div>
                    {m.reason && <p className="mt-1 text-xs text-muted-foreground">{m.reason}</p>}
                  </div>
                </div>
              )
            })}
          </div>
        </ScrollArea>
      </SheetContent>
    </Sheet>
  )
}

// ------------------------------------------------------------------ item form
const EMPTY: StockItemInput = {
  name: '',
  category_id: null,
  unit: 'u',
  min_qty: 0,
  avg_cost_cents: 0,
  default_supplier_id: null,
  track_expiry: false,
  initial_qty: 0,
}

export function StockItemDialog({
  open,
  item,
  onOpenChange,
}: {
  open: boolean
  item: StockItem | null
  onOpenChange: (o: boolean) => void
}) {
  const [form, setForm] = useState<StockItemInput>(EMPTY)
  const [minText, setMinText] = useState('0')
  const [initText, setInitText] = useState('0')
  const cats = useStockCategories()
  const suppliers = useSuppliersLite(open)
  const save = useSaveStockItem()
  const saveCat = useSaveStockCategory()
  const [newCat, setNewCat] = useState<string | null>(null)
  const createCat = () =>
    saveCat.mutate(
      { name: (newCat ?? '').trim() },
      {
        onSuccess: (c) => {
          setForm((f) => ({ ...f, category_id: c.id }))
          setNewCat(null)
        },
      },
    )

  if (useDepsChanged([open, item]) && open) {
    setNewCat(null)
    if (item) {
      setForm({
        name: item.name,
        category_id: item.category_id,
        unit: item.unit,
        min_qty: item.min_qty,
        avg_cost_cents: item.avg_cost_cents,
        default_supplier_id: item.default_supplier_id,
        track_expiry: item.track_expiry,
      })
      setMinText(String(item.min_qty))
    } else {
      setForm(EMPTY)
      setMinText('0')
      setInitText('0')
    }
  }

  const set = <K extends keyof StockItemInput>(k: K, v: StockItemInput[K]) => setForm((f) => ({ ...f, [k]: v }))
  const bu = bulkUnit(form.unit)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{item ? 'Editar insumo' : 'Nuevo insumo'}</DialogTitle>
          <DialogDescription>Los insumos se descuentan con las recetas de los productos.</DialogDescription>
        </DialogHeader>
        <form
          className="grid gap-4"
          onSubmit={(e) => {
            e.preventDefault()
            const data: Partial<StockItemInput> = {
              ...form,
              name: form.name.trim(),
              min_qty: Number(minText.replace(',', '.')) || 0,
            }
            if (!item) data.initial_qty = Number(initText.replace(',', '.')) || 0
            save.mutate({ id: item?.id, data }, { onSuccess: () => onOpenChange(false) })
          }}
        >
          <div className="grid gap-1.5">
            <Label htmlFor="si-name">Nombre</Label>
            <Input id="si-name" autoFocus value={form.name} onChange={(e) => set('name', e.target.value)} placeholder="Ej.: Leche entera" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-1.5">
              <div className="flex items-center justify-between gap-2">
                <Label>Categoría</Label>
                <button
                  type="button"
                  className="text-xs font-medium text-primary hover:underline"
                  onClick={() => setNewCat((v) => (v === null ? '' : null))}
                >
                  {newCat === null ? '+ Nueva' : 'Cancelar'}
                </button>
              </div>
              {newCat !== null && (
                <div className="flex gap-1.5">
                  <Input
                    autoFocus
                    aria-label="Nombre de la categoría nueva"
                    placeholder="Ej.: Lácteos"
                    value={newCat}
                    onChange={(e) => setNewCat(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault()
                        createCat()
                      }
                    }}
                  />
                  <Button type="button" disabled={!newCat.trim() || saveCat.isPending} onClick={createCat}>
                    Crear
                  </Button>
                </div>
              )}
              <Select
                value={form.category_id ? String(form.category_id) : 'none'}
                onValueChange={(v) => set('category_id', v === 'none' ? null : Number(v))}
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">Sin categoría</SelectItem>
                  {cats.data?.map((c) => (
                    <SelectItem key={c.id} value={String(c.id)}>
                      {c.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5">
              <Label>Unidad base</Label>
              <Select value={form.unit} onValueChange={(v) => set('unit', v as Unit)} disabled={!!item}>
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="g">Gramos (g)</SelectItem>
                  <SelectItem value="ml">Mililitros (ml)</SelectItem>
                  <SelectItem value="u">Unidades (u)</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-1.5">
              <Label htmlFor="si-min">Stock mínimo ({form.unit})</Label>
              <Input id="si-min" inputMode="decimal" className="tabular" value={minText} onChange={(e) => setMinText(e.target.value)} />
            </div>
            <div className="grid gap-1.5">
              <Label>Costo por {bu}</Label>
              <MoneyInput
                value={bulkCost(form.avg_cost_cents, form.unit)}
                onChange={(c) => set('avg_cost_cents', (c ?? 0) / bulkFactor(form.unit))}
              />
            </div>
          </div>
          {!item && (
            <div className="grid gap-1.5">
              <Label htmlFor="si-init">Stock inicial ({form.unit})</Label>
              <Input id="si-init" inputMode="decimal" className="tabular" value={initText} onChange={(e) => setInitText(e.target.value)} />
            </div>
          )}
          <div className="grid gap-1.5">
            <Label>Proveedor habitual</Label>
            <Select
              value={form.default_supplier_id ? String(form.default_supplier_id) : 'none'}
              onValueChange={(v) => set('default_supplier_id', v === 'none' ? null : Number(v))}
            >
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">Sin proveedor</SelectItem>
                {suppliers.data?.map((s) => (
                  <SelectItem key={s.id} value={String(s.id)}>
                    {s.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <label className="flex items-center justify-between gap-3 rounded-xl border px-3 py-2.5">
            <span>
              <span className="block text-sm font-medium">Controlar vencimientos</span>
              <span className="block text-xs text-muted-foreground">Pide fecha de vencimiento al recibir compras.</span>
            </span>
            <Switch checked={form.track_expiry} onCheckedChange={(v) => set('track_expiry', v)} />
          </label>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancelar
            </Button>
            <Button type="submit" disabled={!form.name.trim() || save.isPending}>
              Guardar
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
