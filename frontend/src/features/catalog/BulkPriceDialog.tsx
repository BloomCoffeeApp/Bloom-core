import { ArrowRight, Eye, Percent } from 'lucide-react'
import { useEffect, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { fmtMoney, fmtPct } from '@/lib/format'
import { cn } from '@/lib/utils'

import { useBulkPrice, useProductCategories } from './api'
import type { BulkPriceResult } from './types'

const ROUNDINGS = [
  { value: '0', label: 'Sin redondeo' },
  { value: '1000', label: 'A $10' },
  { value: '5000', label: 'A $50' },
  { value: '10000', label: 'A $100' },
  { value: '50000', label: 'A $500' },
]

export function BulkPriceDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const cats = useProductCategories()
  const bulk = useBulkPrice()
  const [category, setCategory] = useState('all')
  const [percent, setPercent] = useState('10')
  const [rounding, setRounding] = useState('5000')
  const [preview, setPreview] = useState<BulkPriceResult | null>(null)

  useEffect(() => {
    if (open) {
      setPreview(null)
      setPercent('10')
      setCategory('all')
      setRounding('5000')
    }
  }, [open])

  // Any parameter change invalidates the preview.
  useEffect(() => setPreview(null), [category, percent, rounding])

  const pct = Number(percent.replace(',', '.'))
  const valid = Number.isFinite(pct) && pct !== 0 && pct > -90
  const body = {
    category_id: category === 'all' ? null : Number(category),
    percent: pct,
    round_to_cents: Number(rounding),
  }
  const changed = preview?.items.filter((i) => i.old_cents !== i.new_cents) ?? []

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle className="font-heading text-xl">Aumento masivo de precios</DialogTitle>
          <DialogDescription>Aplicá un porcentaje a todos los productos activos o a una categoría. Queda registrado en el historial.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="grid gap-1.5">
            <Label>Productos</Label>
            <Select value={category} onValueChange={setCategory}>
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos</SelectItem>
                {cats.data
                  ?.filter((c) => c.active)
                  .map((c) => (
                    <SelectItem key={c.id} value={String(c.id)}>
                      {c.name}
                    </SelectItem>
                  ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="bp-pct">Porcentaje</Label>
            <div className="relative">
              <Input id="bp-pct" inputMode="decimal" className="tabular pr-8" value={percent} onChange={(e) => setPercent(e.target.value)} />
              <Percent className="pointer-events-none absolute top-1/2 right-3 size-3.5 -translate-y-1/2 text-muted-foreground" />
            </div>
          </div>
          <div className="grid gap-1.5">
            <Label>Redondeo</Label>
            <Select value={rounding} onValueChange={setRounding}>
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {ROUNDINGS.map((r) => (
                  <SelectItem key={r.value} value={r.value}>
                    {r.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        {preview ? (
          <div className="space-y-2">
            <p className="text-sm text-muted-foreground">
              {changed.length} de {preview.count} productos cambian de precio.
            </p>
            <ScrollArea className="h-72 rounded-xl border">
              <div className="divide-y">
                {preview.items.map((i) => {
                  const diff = i.old_cents ? ((i.new_cents - i.old_cents) / i.old_cents) * 100 : 0
                  return (
                    <div key={i.product_id} className="flex items-center gap-3 px-3 py-2 text-sm">
                      <span className="min-w-0 flex-1 truncate">{i.name}</span>
                      <span className="tabular text-muted-foreground">{fmtMoney(i.old_cents)}</span>
                      <ArrowRight className="size-3.5 text-muted-foreground" />
                      <span className="tabular w-28 text-right font-semibold">{fmtMoney(i.new_cents)}</span>
                      <span className={cn('tabular w-14 text-right text-xs', diff >= 0 ? 'text-success' : 'text-destructive')}>
                        {diff >= 0 ? '+' : ''}
                        {fmtPct(diff)}
                      </span>
                    </div>
                  )
                })}
              </div>
            </ScrollArea>
          </div>
        ) : (
          <div className="flex h-32 items-center justify-center rounded-xl border border-dashed text-sm text-muted-foreground">
            Generá la vista previa para ver los precios antes y después.
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          {!preview ? (
            <Button disabled={!valid || bulk.isPending} onClick={() => bulk.mutate({ ...body, dry_run: true }, { onSuccess: setPreview })}>
              <Eye /> Vista previa
            </Button>
          ) : (
            <Button
              disabled={!changed.length || bulk.isPending}
              onClick={() => bulk.mutate({ ...body, dry_run: false }, { onSuccess: () => onOpenChange(false) })}
            >
              Aplicar a {changed.length} productos
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
