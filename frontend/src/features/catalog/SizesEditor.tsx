import { ChevronDown, Info, RotateCcw, Ruler, Star, Trash2 } from 'lucide-react'
import { useState } from 'react'

import { MoneyInput } from '@/components/money-input'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { fmtMoney, fmtPct } from '@/lib/format'
import { cn } from '@/lib/utils'

import type { StockItem } from '../stock/types'
import { StockItemPicker } from '../stock/components'
import { marginOf, marginTextClass } from './catalog-utils'
import { effectiveRecipe, fmtQty, fmtScale, num, type SizeDraft } from './size-utils'
import type { Size } from './types'

/**
 * "Tamaños" section of the product editor: which catalog sizes the product is sold in, each with
 * its price and its recipe (the base recipe × a factor, with per-ingredient overrides).
 */
export function SizesEditor({
  sizes,
  drafts,
  onChange,
  defaultId,
  onDefault,
  base,
  stock,
}: {
  sizes: Size[]
  drafts: SizeDraft[]
  onChange: (d: SizeDraft[]) => void
  defaultId: number | null
  onDefault: (id: number) => void
  /** Base recipe (product recipe + resale item): stock_item_id → qty. */
  base: Map<number, number>
  stock: StockItem[] | undefined
}) {
  const [openId, setOpenId] = useState<number | null>(null)
  const byId = new Map(stock?.map((s) => [s.id, s]))
  const sizeById = new Map(sizes.map((s) => [s.id, s]))
  const patch = (id: number, p: Partial<SizeDraft>) => onChange(drafts.map((d) => (d.size_id === id ? { ...d, ...p } : d)))
  const enabled = drafts.filter((d) => d.enabled)
  const ref = enabled.find((d) => d.size_id === defaultId) ?? enabled[0]
  const refMl = ref ? sizeById.get(ref.size_id)?.volume_ml : null
  const canScaleByVolume = !!refMl && enabled.some((d) => d !== ref && sizeById.get(d.size_id)?.volume_ml)

  const scaleByVolume = () => {
    if (!refMl || !ref) return
    const refScale = num(ref.scale) || 1
    onChange(
      drafts.map((d) => {
        const ml = sizeById.get(d.size_id)?.volume_ml
        return d.enabled && ml && d !== ref ? { ...d, scale: fmtQty((ml / refMl) * refScale) } : d
      }),
    )
  }

  return (
    <div className="space-y-2">
      {canScaleByVolume && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-muted/60 px-3 py-2 text-xs text-muted-foreground">
          <span>Tip: la receta de arriba es la del tamaño “×1”. Podés calcular el factor de cada tamaño según su volumen.</span>
          <Button type="button" variant="outline" size="sm" onClick={scaleByVolume}>
            <Ruler /> Escalar por volumen
          </Button>
        </div>
      )}
      {drafts.map((d) => {
        const s = sizeById.get(d.size_id)
        if (!s) return null
        const eff = effectiveRecipe(base, d)
        const cost = Math.round([...eff].reduce((a, [sid, q]) => a + q * (byId.get(sid)?.avg_cost_cents ?? 0), 0))
        const margin = marginOf(d.price ?? 0, cost)
        const isDefault = d.enabled && d.size_id === (ref?.size_id ?? null)
        const open = openId === d.size_id && d.enabled
        const overridden = Object.keys(d.overrides).length
        return (
          <div
            key={d.size_id}
            data-testid={`size-row-${s.short_label}`}
            className={cn('rounded-xl border transition-colors', d.enabled ? 'border-primary/40 bg-primary/5' : 'opacity-80')}
          >
            <div className="space-y-2 p-3">
              <div className="flex items-center gap-3">
                <Checkbox
                  checked={d.enabled}
                  aria-label={`Vender en ${s.name}`}
                  onCheckedChange={(v) => {
                    patch(d.size_id, { enabled: !!v })
                    if (v && !enabled.length) onDefault(d.size_id)
                  }}
                />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">
                    {s.name}
                    {!s.active && <span className="ml-1.5 text-xs font-normal text-muted-foreground">(inactivo)</span>}
                  </p>
                  {d.enabled && (
                    <p className="text-xs text-muted-foreground">
                      Costo <span className="tabular">{fmtMoney(cost)}</span> · margen{' '}
                      <span className={cn('tabular', marginTextClass(margin))}>{fmtPct(margin)}</span>
                    </p>
                  )}
                </div>
                {d.enabled && (
                  <div className="flex shrink-0 items-center gap-1">
                    <Button
                      type="button"
                      variant={isDefault ? 'secondary' : 'ghost'}
                      size="icon"
                      aria-label={isDefault ? `${s.name} es el predeterminado` : `Usar ${s.name} como predeterminado`}
                      aria-pressed={isDefault}
                      title="Tamaño predeterminado en el POS"
                      onClick={() => onDefault(d.size_id)}
                    >
                      <Star className={cn(isDefault && 'fill-primary text-primary')} />
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      aria-label={`Receta de ${s.name}`}
                      aria-expanded={open}
                      onClick={() => setOpenId(open ? null : d.size_id)}
                    >
                      <ChevronDown className={cn('transition-transform', open && 'rotate-180')} />
                    </Button>
                  </div>
                )}
              </div>
              {d.enabled && (
                <div className="grid grid-cols-[minmax(0,1fr)_6.5rem] gap-2 pl-7">
                  <MoneyInput
                    aria-label={`Precio ${s.name}`}
                    value={d.price}
                    onChange={(price) => patch(d.size_id, { price })}
                    className="[&_input]:font-semibold"
                  />
                  <div className="relative" title="Factor de la receta base">
                    <span className="pointer-events-none absolute top-1/2 left-2.5 -translate-y-1/2 text-xs text-muted-foreground">receta ×</span>
                    <Input
                      aria-label={`Factor de receta ${s.name}`}
                      inputMode="decimal"
                      className="tabular h-9 pl-14"
                      value={d.scale}
                      onChange={(e) => patch(d.size_id, { scale: e.target.value })}
                    />
                  </div>
                </div>
              )}
            </div>
            {open && (
              <div className="space-y-2 border-t border-dashed px-3 pt-2 pb-3">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-xs text-muted-foreground">
                    Receta de {s.short_label}: base {fmtScale(d.scale)}
                    {overridden ? ` · ${overridden} ${overridden === 1 ? 'ajuste' : 'ajustes'} a mano` : ''}. Cambiá una cantidad para fijarla.
                  </p>
                  {overridden > 0 && (
                    <Button type="button" variant="ghost" size="sm" onClick={() => patch(d.size_id, { overrides: {} })}>
                      <RotateCcw /> Volver a escalar
                    </Button>
                  )}
                </div>
                {[...new Set([...base.keys(), ...Object.keys(d.overrides).map(Number)])].map((sid) => {
                  const item = byId.get(sid)
                  const over = d.overrides[sid]
                  const scaled = (base.get(sid) ?? 0) * (num(d.scale) || 1)
                  const value = over ?? fmtQty(scaled)
                  const line = num(value) * (item?.avg_cost_cents ?? 0)
                  return (
                    <div key={sid} className="grid grid-cols-[minmax(0,1fr)_6.5rem_5rem_2.25rem] items-center gap-2 text-sm">
                      <span className={cn('truncate', over === '0' && 'text-muted-foreground line-through')}>
                        {item?.name ?? '?'}
                        {over != null && <span className="ml-1.5 text-xs text-primary">ajustado</span>}
                      </span>
                      <div className="relative">
                        <Input
                          aria-label={`Cantidad de ${item?.name ?? 'insumo'} en ${s.name}`}
                          inputMode="decimal"
                          className="tabular h-8 pr-8"
                          value={value}
                          onChange={(e) => patch(d.size_id, { overrides: { ...d.overrides, [sid]: e.target.value } })}
                        />
                        <span className="pointer-events-none absolute top-1/2 right-2.5 -translate-y-1/2 text-xs text-muted-foreground">
                          {item?.unit ?? ''}
                        </span>
                      </div>
                      <span className="tabular text-right text-xs">{fmtMoney(Math.round(line))}</span>
                      {over != null && base.has(sid) ? (
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          aria-label="Volver a la cantidad escalada"
                          onClick={() => {
                            const rest = { ...d.overrides }
                            delete rest[sid]
                            patch(d.size_id, { overrides: rest })
                          }}
                        >
                          <RotateCcw className="text-muted-foreground" />
                        </Button>
                      ) : (
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          aria-label="No usar en este tamaño"
                          onClick={() => {
                            const rest = { ...d.overrides }
                            if (base.has(sid)) rest[sid] = '0'
                            else delete rest[sid]
                            patch(d.size_id, { overrides: rest })
                          }}
                        >
                          <Trash2 className="text-muted-foreground" />
                        </Button>
                      )}
                    </div>
                  )
                })}
                <StockItemPicker
                  items={stock}
                  value={null}
                  placeholder="Agregar un insumo solo para este tamaño…"
                  excludeIds={[...new Set([...base.keys(), ...Object.keys(d.overrides).map(Number)])]}
                  onChange={(i) => patch(d.size_id, { overrides: { ...d.overrides, [i.id]: '' } })}
                />
              </div>
            )}
          </div>
        )
      })}
      {!drafts.length && (
        <p className="text-sm text-muted-foreground">
          Todavía no hay tamaños. Crealos en la pestaña <span className="font-medium">Tamaños</span>.
        </p>
      )}
      <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <Info className="size-3 shrink-0" /> Los modificadores (leche, extras) se suman arriba del precio del tamaño y sus insumos se escalan con el factor.
      </p>
    </div>
  )
}
