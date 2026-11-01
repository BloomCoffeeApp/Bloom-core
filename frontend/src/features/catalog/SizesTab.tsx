import { CupSoda, Pencil, Plus } from 'lucide-react'
import { useState } from 'react'

import { EmptyState } from '@/components/empty-state'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Switch } from '@/components/ui/switch'
import { useDepsChanged } from '@/hooks/use-deps-changed'
import { cn } from '@/lib/utils'

import { useSaveSize, useSizes } from './api'
import { volumeText } from './catalog-utils'
import type { Size, SizeInput } from './types'

const EMPTY: SizeInput = { name: '', short_label: '', volume_ml: null, sort_order: 0, active: true }

function SizeDialog({
  open,
  onOpenChange,
  size,
  nextOrder,
}: {
  open: boolean
  onOpenChange: (o: boolean) => void
  size: Size | null
  nextOrder: number
}) {
  const save = useSaveSize()
  const [form, setForm] = useState<SizeInput>(EMPTY)
  const [ml, setMl] = useState('')
  if (useDepsChanged([open, size, nextOrder]) && open) {
    setForm(size ? { ...size } : { ...EMPTY, sort_order: nextOrder })
    setMl(size?.volume_ml ? String(size.volume_ml) : '')
  }
  const mlNum = ml.trim() ? Math.round(Number(ml.replace(',', '.'))) : null
  const mlValid = mlNum == null || (Number.isFinite(mlNum) && mlNum >= 1 && mlNum <= 10000)
  const valid = form.name.trim() && form.short_label.trim() && mlValid
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{size ? 'Editar tamaño' : 'Nuevo tamaño'}</DialogTitle>
          <DialogDescription>Después elegí en cada producto en qué tamaños se vende y a qué precio.</DialogDescription>
        </DialogHeader>
        <form
          className="grid gap-4"
          onSubmit={(e) => {
            e.preventDefault()
            if (!valid) return
            save.mutate(
              { id: size?.id, data: { ...form, name: form.name.trim(), short_label: form.short_label.trim(), volume_ml: mlNum } },
              { onSuccess: () => onOpenChange(false) },
            )
          }}
        >
          <div className="grid grid-cols-[1fr_7rem] gap-3">
            <div className="grid gap-1.5">
              <Label htmlFor="size-name">Nombre</Label>
              <Input
                id="size-name"
                autoFocus
                placeholder="Ej.: Grande 16 oz"
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="size-label">Abreviatura</Label>
              <Input
                id="size-label"
                maxLength={12}
                placeholder="Ej.: G"
                value={form.short_label}
                onChange={(e) => setForm((f) => ({ ...f, short_label: e.target.value }))}
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-1.5">
              <Label htmlFor="size-ml">Volumen en ml (opcional)</Label>
              <Input id="size-ml" inputMode="numeric" className="tabular" placeholder="Ej.: 480" value={ml} onChange={(e) => setMl(e.target.value)} />
              {mlNum != null && mlValid && <p className="text-xs text-muted-foreground">{volumeText(mlNum)}</p>}
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="size-order">Orden</Label>
              <Input
                id="size-order"
                type="number"
                className="tabular"
                value={form.sort_order}
                onChange={(e) => setForm((f) => ({ ...f, sort_order: Number(e.target.value) || 0 }))}
              />
            </div>
          </div>
          <label className="flex items-center justify-between gap-3 rounded-xl border px-3 py-2.5">
            <span>
              <span className="block text-sm font-medium">Activo</span>
              <span className="block text-xs text-muted-foreground">Si lo desactivás deja de ofrecerse en el POS y en el menú.</span>
            </span>
            <Switch checked={form.active} onCheckedChange={(active) => setForm((f) => ({ ...f, active }))} />
          </label>
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

export function SizesTab() {
  const { data, isLoading } = useSizes()
  const [editing, setEditing] = useState<Size | null>(null)
  const [open, setOpen] = useState(false)
  const nextOrder = (data?.reduce((m, s) => Math.max(m, s.sort_order), -1) ?? -1) + 1
  const show = (s: Size | null) => {
    setEditing(s)
    setOpen(true)
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap justify-between gap-2">
        <p className="text-sm text-muted-foreground">
          Tus tamaños (8, 12, 16 oz o en ml). Cada producto elige en cuáles se vende, con su precio y su receta.
        </p>
        <Button onClick={() => show(null)}>
          <Plus /> Nuevo tamaño
        </Button>
      </div>
      {isLoading ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-24 rounded-2xl" />
          ))}
        </div>
      ) : !data?.length ? (
        <EmptyState
          icon={CupSoda}
          title="Sin tamaños"
          description="Creá tamaños como Chico 8 oz, Mediano 12 oz o Grande 16 oz para vender un mismo producto en distintas medidas."
          action={
            <Button variant="outline" onClick={() => show(null)}>
              <Plus /> Crear el primero
            </Button>
          }
        />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {data.map((s) => (
            <Card key={s.id} className={cn('rounded-2xl', !s.active && 'opacity-60')} data-testid="size-card">
              <CardContent className="flex items-center gap-4">
                <div className="flex size-12 shrink-0 items-center justify-center rounded-2xl bg-primary/10 font-heading text-lg font-semibold text-primary">
                  {s.short_label}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium">{s.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {[volumeText(s.volume_ml), `${s.product_count} ${s.product_count === 1 ? 'producto' : 'productos'}`]
                      .filter(Boolean)
                      .join(' · ')}
                  </p>
                </div>
                {!s.active && <Badge variant="outline">Inactivo</Badge>}
                <Button variant="ghost" size="icon" aria-label={`Editar ${s.name}`} onClick={() => show(s)}>
                  <Pencil />
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
      <SizeDialog open={open} onOpenChange={setOpen} size={editing} nextOrder={nextOrder} />
    </div>
  )
}
