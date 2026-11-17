import { Check, Minus, Plus } from 'lucide-react'
import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { fmtMoney } from '@/lib/format'
import { cn } from '@/lib/utils'

import type { PosModifier, PosModifierGroup, PosProduct, PosSize } from './types'

function groupHint(g: PosModifierGroup) {
  if (g.min_select > 0 && g.min_select === g.max_select) return `Elegí ${g.min_select}`
  if (g.min_select > 0) return `Elegí entre ${g.min_select} y ${g.max_select}`
  if (g.max_select === 1) return 'Opcional'
  return `Opcional · hasta ${g.max_select}`
}

function ModifierBody({
  product,
  onConfirm,
  onCancel,
}: {
  product: PosProduct
  onConfirm: (mods: PosModifier[], qty: number, notes: string, size: PosSize | null) => void
  onCancel: () => void
}) {
  const [sizeId, setSizeId] = useState<number | null>(
    () => (product.sizes.find((s) => s.is_default) ?? product.sizes[0])?.size_id ?? null,
  )
  const size = product.sizes.find((s) => s.size_id === sizeId) ?? null
  const [selected, setSelected] = useState<Record<number, number[]>>(() => {
    // Preselect the first option of required single-choice groups.
    const init: Record<number, number[]> = {}
    for (const g of product.modifier_groups) {
      if (g.min_select === 1 && g.max_select === 1 && g.modifiers[0]) init[g.id] = [g.modifiers[0].id]
    }
    return init
  })
  const [qty, setQty] = useState(1)
  const [notes, setNotes] = useState('')

  const toggle = (g: PosModifierGroup, m: PosModifier) => {
    setSelected((s) => {
      const cur = s[g.id] ?? []
      if (cur.includes(m.id)) {
        if (g.max_select === 1 && g.min_select === 1) return s
        return { ...s, [g.id]: cur.filter((x) => x !== m.id) }
      }
      if (g.max_select === 1) return { ...s, [g.id]: [m.id] }
      if (g.max_select > 0 && cur.length >= g.max_select) return s
      return { ...s, [g.id]: [...cur, m.id] }
    })
  }

  const mods = product.modifier_groups.flatMap((g) => g.modifiers.filter((m) => (selected[g.id] ?? []).includes(m.id)))
  const unit = (size ? size.price_cents : product.price_cents) + mods.reduce((a, m) => a + m.price_delta_cents, 0)
  const missing = product.modifier_groups.filter((g) => (selected[g.id]?.length ?? 0) < g.min_select)

  return (
    <>
      <DialogHeader>
        <DialogTitle className="font-heading text-2xl">{product.name}</DialogTitle>
        <DialogDescription>
          {size ? `${size.name} · ${fmtMoney(size.price_cents)}` : `Precio base ${fmtMoney(product.price_cents)}`}
        </DialogDescription>
      </DialogHeader>
      <div className="max-h-[55vh] space-y-5 overflow-y-auto pr-1">
        {product.sizes.length > 0 && (
          <div className="space-y-2" role="radiogroup" aria-label="Tamaño">
            <p className="font-medium">Tamaño</p>
            <div className={cn('grid gap-2', product.sizes.length > 3 ? 'grid-cols-2 sm:grid-cols-4' : 'grid-cols-3')}>
              {product.sizes.map((s) => {
                const on = s.size_id === sizeId
                return (
                  <button
                    key={s.size_id}
                    type="button"
                    role="radio"
                    aria-checked={on}
                    aria-label={`${s.name} ${fmtMoney(s.price_cents)}`}
                    onClick={() => setSizeId(s.size_id)}
                    className={cn(
                      'touch-target flex min-h-20 flex-col items-center justify-center gap-0.5 rounded-2xl border px-2 py-2 text-center transition-colors',
                      on ? 'border-primary bg-primary/10 ring-2 ring-primary/30' : 'hover:bg-muted',
                    )}
                  >
                    <span className={cn('font-heading text-2xl leading-none font-semibold', on && 'text-primary')}>{s.short_label}</span>
                    <span className="text-xs leading-tight text-muted-foreground">{s.name}</span>
                    <span className="tabular text-sm font-semibold">{fmtMoney(s.price_cents, { short: true })}</span>
                  </button>
                )
              })}
            </div>
          </div>
        )}
        {product.modifier_groups.map((g) => {
          const cur = selected[g.id] ?? []
          const full = g.max_select > 1 && cur.length >= g.max_select
          return (
            <div key={g.id} className="space-y-2">
              <div className="flex items-baseline justify-between">
                <p className="font-medium">{g.name}</p>
                <span className={cn('text-xs', cur.length < g.min_select ? 'text-destructive' : 'text-muted-foreground')}>
                  {groupHint(g)}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                {g.modifiers.map((m) => {
                  const on = cur.includes(m.id)
                  return (
                    <button
                      key={m.id}
                      type="button"
                      onClick={() => toggle(g, m)}
                      disabled={!on && full}
                      className={cn(
                        'touch-target flex min-h-14 items-center justify-between gap-2 rounded-xl border px-3 py-2 text-left text-sm transition-colors disabled:opacity-40',
                        on ? 'border-primary bg-primary/10 ring-2 ring-primary/30' : 'hover:bg-muted',
                      )}
                    >
                      <span className="font-medium">{m.name}</span>
                      <span className="flex items-center gap-1 text-xs text-muted-foreground">
                        {m.price_delta_cents !== 0 && `+${fmtMoney(m.price_delta_cents, { short: true })}`}
                        {on && <Check className="size-4 text-primary" />}
                      </span>
                    </button>
                  )
                })}
              </div>
            </div>
          )
        })}
        <div className="space-y-2">
          <Label htmlFor="mod-notes">Nota para barra</Label>
          <Textarea id="mod-notes" rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Ej.: bien caliente, sin espuma…" />
        </div>
      </div>
      {/* flex-wrap: on a phone the quantity stepper and the two buttons do not fit in one row (they used to widen the
          whole dialog and get it clipped), so the buttons drop to their own row. */}
      <DialogFooter className="flex-row flex-wrap items-center gap-3 sm:justify-between">
        <div className="flex items-center gap-2">
          <Button variant="outline" size="icon-lg" className="size-12" onClick={() => setQty((q) => Math.max(1, q - 1))} aria-label="Restar">
            <Minus />
          </Button>
          <span className="tabular w-8 text-center text-xl font-semibold">{qty}</span>
          <Button variant="outline" size="icon-lg" className="size-12" onClick={() => setQty((q) => q + 1)} aria-label="Sumar">
            <Plus />
          </Button>
        </div>
        <div className="ml-auto flex gap-2">
          <Button variant="ghost" className="h-12 px-4" onClick={onCancel}>
            Cancelar
          </Button>
          <Button className="h-12 px-6 text-base" disabled={missing.length > 0} onClick={() => onConfirm(mods, qty, notes, size)}>
            Agregar · {fmtMoney(unit * qty)}
          </Button>
        </div>
      </DialogFooter>
    </>
  )
}

export function ModifierDialog({
  product,
  onOpenChange,
  onConfirm,
}: {
  product: PosProduct | null
  onOpenChange: (o: boolean) => void
  onConfirm: (p: PosProduct, mods: PosModifier[], qty: number, notes: string, size: PosSize | null) => void
}) {
  return (
    <Dialog open={product != null} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl">
        {product && (
          <ModifierBody
            key={product.id}
            product={product}
            onCancel={() => onOpenChange(false)}
            onConfirm={(mods, qty, notes, size) => {
              onConfirm(product, mods, qty, notes, size)
              onOpenChange(false)
            }}
          />
        )}
      </DialogContent>
    </Dialog>
  )
}
