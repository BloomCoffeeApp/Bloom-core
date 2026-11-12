import { Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'

import { MoneyInput } from '@/components/money-input'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { useDepsChanged } from '@/hooks/use-deps-changed'
import { fmtDate, fmtMoney, fmtNumber, fmtQty } from '@/lib/format'
import { cn } from '@/lib/utils'

import { useQuickDiscard, useQuickItems, useRegisterWaste, useSavePackages, useStockLots } from './api'
import { DISCARD_REASONS, defaultPackage, fmtPackages } from './stock-utils'
import type { DiscardReason, PackageInput, StockItem } from './types'

const num = (s: string) => {
  const n = Number(s.replace(',', '.'))
  return Number.isFinite(n) ? n : 0
}

export function ReasonChips({ value, onChange }: { value: DiscardReason | null; onChange: (r: DiscardReason) => void }) {
  return (
    <div className="flex flex-wrap gap-1.5" role="radiogroup" aria-label="Motivo">
      {DISCARD_REASONS.map((r) => (
        <button
          key={r.value}
          type="button"
          role="radio"
          aria-checked={value === r.value}
          onClick={() => onChange(r.value)}
          className={cn(
            'min-h-9 rounded-full border px-3 py-1 text-sm transition-colors',
            value === r.value ? 'border-primary bg-primary/10 text-primary' : 'hover:bg-muted',
          )}
        >
          {r.label}
        </button>
      ))}
    </div>
  )
}

type Mode = 'qty' | 'packages' | 'all'

/** Stock → Descartar: everything left, an amount or N packages (optionally of one lot), with a reason.
 * Recorded as a merma (shows in the losses reports and in the month result). */
export function DiscardDialog({ item, onOpenChange }: { item: StockItem | null; onOpenChange: (o: boolean) => void }) {
  const waste = useRegisterWaste()
  const lots = useStockLots(item?.track_expiry ? item.id : null)
  const [mode, setMode] = useState<Mode>('qty')
  const [qty, setQty] = useState('')
  const [packageId, setPackageId] = useState<number | null>(null)
  const [reason, setReason] = useState<DiscardReason | null>(null)
  const [note, setNote] = useState('')
  const [lotId, setLotId] = useState<number | null>(null)

  if (useDepsChanged([item]) && item) {
    setMode('qty')
    setQty('')
    setPackageId(defaultPackage(item.packages)?.id ?? null)
    setReason(null)
    setNote('')
    setLotId(null)
  }
  if (!item) return null
  const pkg = item.packages.find((p) => p.id === packageId)
  const lot = lots.data?.find((l) => l.id === lotId)
  const base =
    mode === 'all'
      ? lot
        ? lot.qty_remaining
        : Math.max(item.current_qty, 0)
      : mode === 'packages'
        ? num(qty) * (pkg?.content_qty ?? 0)
        : num(qty)
  const valid = base > 0 && !!reason && (reason !== 'other' || note.trim().length > 0) && (!lot || base <= lot.qty_remaining + 1e-9)

  return (
    <Dialog open={!!item} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Descartar {item.name}</DialogTitle>
          <DialogDescription>Hay {fmtPackages(item.current_qty, item.unit, item.packages)}. Queda registrado como merma.</DialogDescription>
        </DialogHeader>
        <form
          className="grid gap-4"
          onSubmit={(e) => {
            e.preventDefault()
            if (!valid) return
            waste.mutate(
              {
                stock_item_id: item.id,
                ...(mode === 'all' ? { all: true } : mode === 'packages' ? { package_id: pkg!.id, packages: num(qty) } : { qty: num(qty) }),
                lot_id: lotId,
                reason_code: reason!,
                note: note.trim() || null,
              },
              { onSuccess: () => onOpenChange(false) },
            )
          }}
        >
          <ToggleGroup
            type="single"
            variant="outline"
            value={mode}
            onValueChange={(v) => v && (setMode(v as Mode), setQty(''))}
            className="w-full"
          >
            <ToggleGroupItem value="qty" className="flex-1">
              Cantidad
            </ToggleGroupItem>
            {item.packages.length > 0 && (
              <ToggleGroupItem value="packages" className="flex-1">
                Envases
              </ToggleGroupItem>
            )}
            <ToggleGroupItem value="all" className="flex-1">
              Todo
            </ToggleGroupItem>
          </ToggleGroup>

          {item.track_expiry && (lots.data?.length ?? 0) > 0 && (
            <div className="grid gap-1.5">
              <Label htmlFor="d-lot">Lote</Label>
              <Select value={lotId ? String(lotId) : 'any'} onValueChange={(v) => setLotId(v === 'any' ? null : Number(v))}>
                <SelectTrigger id="d-lot" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="any">Cualquiera (primero el que vence antes)</SelectItem>
                  {lots.data!.map((l) => (
                    <SelectItem key={l.id} value={String(l.id)}>
                      {fmtQty(l.qty_remaining, item.unit)} · {l.expiry_date ? `vence ${fmtDate(l.expiry_date)}` : 'sin vencimiento'}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          {mode === 'qty' && (
            <div className="grid gap-1.5">
              <Label htmlFor="d-qty">Cantidad ({item.unit})</Label>
              <Input id="d-qty" inputMode="decimal" autoFocus className="tabular" value={qty} onChange={(e) => setQty(e.target.value)} />
            </div>
          )}
          {mode === 'packages' && (
            <div className="grid grid-cols-[6rem_1fr] gap-2">
              <div className="grid gap-1.5">
                <Label htmlFor="d-pk">Envases</Label>
                <Input id="d-pk" inputMode="decimal" autoFocus className="tabular" value={qty} onChange={(e) => setQty(e.target.value)} />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="d-pkg">de</Label>
                <Select value={packageId ? String(packageId) : ''} onValueChange={(v) => setPackageId(Number(v))}>
                  <SelectTrigger id="d-pkg" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {item.packages.map((p) => (
                      <SelectItem key={p.id} value={String(p.id)}>
                        {p.name} ({fmtQty(p.content_qty, item.unit)})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          )}

          <div className="grid gap-1.5">
            <Label>Motivo</Label>
            <ReasonChips value={reason} onChange={setReason} />
            <Input
              aria-label="Detalle"
              placeholder={reason === 'other' ? 'Contá qué pasó (obligatorio)' : 'Detalle (opcional)'}
              maxLength={300}
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
          </div>
          {base > 0 && (
            <div className="flex items-center justify-between rounded-xl bg-destructive/10 px-3 py-2 text-sm text-destructive">
              <span>
                Se descartan {fmtQty(base, item.unit)}
                {lot && base > lot.qty_remaining + 1e-9 ? ' (más de lo que tiene el lote)' : ''}
              </span>
              <span className="tabular font-semibold">{fmtMoney(Math.round(base * item.avg_cost_cents))}</span>
            </div>
          )}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancelar
            </Button>
            <Button type="submit" variant="destructive" disabled={!valid || waste.isPending}>
              Descartar
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// ------------------------------------------------------------------ package types
interface PkgRow {
  key: string
  id: number | null
  name: string
  content: string
  barcode: string
  cost: number | null
  is_default: boolean
}
let seq = 0
const row = (p?: Partial<PkgRow>): PkgRow => ({
  key: `p${++seq}`,
  id: null,
  name: '',
  content: '',
  barcode: '',
  cost: null,
  is_default: false,
  ...p,
})

/** "6 leches de 1 L", "caja de 6 × 250 ml": how this item is bought and stored. Stock stays in its base unit. */
export function PackagesDialog({ item, onOpenChange }: { item: StockItem | null; onOpenChange: (o: boolean) => void }) {
  const save = useSavePackages()
  const [rows, setRows] = useState<PkgRow[]>([])
  if (useDepsChanged([item]) && item) {
    setRows(
      item.packages.length
        ? item.packages.map((p) =>
            row({
              id: p.id,
              name: p.name,
              content: String(p.content_qty),
              barcode: p.barcode ?? '',
              cost: p.cost_cents,
              is_default: p.is_default,
            }),
          )
        : [row({ is_default: true })],
    )
  }
  if (!item) return null
  const update = (key: string, patch: Partial<PkgRow>) => setRows(rows.map((r) => (r.key === key ? { ...r, ...patch } : r)))
  const filled = rows.filter((r) => r.name.trim() || r.content.trim())
  const valid = filled.every((r) => r.name.trim() && num(r.content) > 0)
  return (
    <Dialog open={!!item} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Envases de {item.name}</DialogTitle>
          <DialogDescription>
            El stock sigue en {item.unit}; los envases sirven para cargar compras, contar y ver el stock como «4 × Sachet 1 L + 730 ml».
          </DialogDescription>
        </DialogHeader>
        <form
          className="grid gap-3"
          onSubmit={(e) => {
            e.preventDefault()
            if (!valid) return
            const packages: PackageInput[] = filled.map((r) => ({
              id: r.id,
              name: r.name.trim(),
              content_qty: num(r.content),
              barcode: r.barcode.trim() || null,
              cost_cents: r.cost,
              is_default: r.is_default,
            }))
            save.mutate({ id: item.id, packages }, { onSuccess: () => onOpenChange(false) })
          }}
        >
          <div className="hidden grid-cols-[minmax(0,1fr)_7rem_8rem_8rem_5rem_2.5rem] gap-2 px-1 text-xs font-medium text-muted-foreground uppercase sm:grid">
            <span>Nombre</span>
            <span>Contenido ({item.unit})</span>
            <span>Código de barras</span>
            <span>Costo por envase</span>
            <span>Principal</span>
            <span />
          </div>
          {rows.map((r, i) => (
            <div
              key={r.key}
              className="grid grid-cols-2 items-center gap-2 rounded-xl border p-2 sm:grid-cols-[minmax(0,1fr)_7rem_8rem_8rem_5rem_2.5rem] sm:border-0 sm:p-0"
            >
              <Input
                aria-label={`Nombre del envase ${i + 1}`}
                placeholder="Ej.: Sachet 1 L"
                maxLength={60}
                className="col-span-2 sm:col-span-1"
                value={r.name}
                onChange={(e) => update(r.key, { name: e.target.value })}
              />
              <Input
                aria-label={`Contenido del envase ${i + 1}`}
                inputMode="decimal"
                placeholder={item.unit === 'u' ? '6' : '1000'}
                className="tabular"
                value={r.content}
                onChange={(e) => update(r.key, { content: e.target.value })}
              />
              <Input
                aria-label={`Código de barras del envase ${i + 1}`}
                maxLength={40}
                value={r.barcode}
                onChange={(e) => update(r.key, { barcode: e.target.value })}
              />
              <MoneyInput aria-label={`Costo del envase ${i + 1}`} value={r.cost} onChange={(c) => update(r.key, { cost: c })} />
              <label className="flex items-center gap-1.5 text-sm">
                <input
                  type="radio"
                  name="pkg-default"
                  className="size-4 accent-[var(--primary)]"
                  checked={r.is_default}
                  onChange={() => setRows(rows.map((x) => ({ ...x, is_default: x.key === r.key })))}
                />
                <span className="sm:sr-only">Principal</span>
              </label>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                aria-label={`Quitar envase ${i + 1}`}
                onClick={() => setRows(rows.length > 1 ? rows.filter((x) => x.key !== r.key) : [row({ is_default: true })])}
              >
                <Trash2 className="text-muted-foreground" />
              </Button>
              {num(r.content) > 0 && (
                <span className="col-span-2 text-xs text-muted-foreground sm:col-span-6">
                  = {fmtQty(num(r.content), item.unit)}
                  {r.cost
                    ? ` · ${fmtMoney(Math.round((r.cost / num(r.content)) * (item.unit === 'u' ? 1 : 1000)))} por ${item.unit === 'g' ? 'kg' : item.unit === 'ml' ? 'L' : 'u'}`
                    : ''}
                </span>
              )}
            </div>
          ))}
          <div>
            <Button type="button" variant="outline" size="sm" onClick={() => setRows([...rows, row()])} disabled={rows.length >= 20}>
              <Plus /> Otro envase
            </Button>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancelar
            </Button>
            <Button type="submit" disabled={!valid || save.isPending}>
              Guardar envases
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// ------------------------------------------------------------------ quick discard (POS / barista)
/** Small spills from the POS or the barista screen ("se cayeron 10 ml de leche"). Up to 1 L / 1 kg / 10 u. */
export function QuickDiscardDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const items = useQuickItems(open)
  const discard = useQuickDiscard()
  const [itemId, setItemId] = useState<number | null>(null)
  const [qty, setQty] = useState('')
  const [reason, setReason] = useState<DiscardReason>('spill')
  const [note, setNote] = useState('')
  if (useDepsChanged([open]) && open) {
    setItemId(null)
    setQty('')
    setReason('spill')
    setNote('')
  }
  const item = items.data?.find((i) => i.id === itemId)
  const presets = item?.unit === 'u' ? [1, 2] : [10, 50, 100]
  const n = num(qty)
  const valid = !!item && n > 0 && (reason !== 'other' || note.trim().length > 0)
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Descartar insumo</DialogTitle>
          <DialogDescription>Para derrames y pequeñas pérdidas del turno. Queda registrado como merma.</DialogDescription>
        </DialogHeader>
        <form
          className="grid gap-4"
          onSubmit={(e) => {
            e.preventDefault()
            if (valid)
              discard.mutate(
                {
                  stock_item_id: item!.id,
                  qty: n,
                  reason_code: reason,
                  note: note.trim() || null,
                },
                { onSuccess: () => onOpenChange(false) },
              )
          }}
        >
          <div className="grid gap-1.5">
            <Label htmlFor="qd-item">Insumo</Label>
            <Select value={itemId ? String(itemId) : ''} onValueChange={(v) => setItemId(Number(v))}>
              <SelectTrigger id="qd-item" className="h-11 w-full">
                <SelectValue placeholder="Elegí el insumo (leche, café…)" />
              </SelectTrigger>
              <SelectContent>
                {items.data?.map((i) => (
                  <SelectItem key={i.id} value={String(i.id)}>
                    {i.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="qd-qty">Cantidad{item ? ` (${item.unit})` : ''}</Label>
            <div className="flex gap-2">
              <Input id="qd-qty" inputMode="decimal" className="tabular h-11" value={qty} onChange={(e) => setQty(e.target.value)} />
              {item &&
                presets.map((p) => (
                  <Button key={p} type="button" variant="outline" className="h-11" onClick={() => setQty(String(p))}>
                    {fmtNumber(p)} {item.unit}
                  </Button>
                ))}
            </div>
          </div>
          <div className="grid gap-1.5">
            <Label>Motivo</Label>
            <ReasonChips value={reason} onChange={setReason} />
            <Input
              aria-label="Detalle"
              placeholder={reason === 'other' ? 'Contá qué pasó (obligatorio)' : 'Detalle (opcional)'}
              maxLength={300}
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" className="h-11" onClick={() => onOpenChange(false)}>
              Cancelar
            </Button>
            <Button type="submit" variant="destructive" className="h-11" disabled={!valid || discard.isPending}>
              Descartar
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
