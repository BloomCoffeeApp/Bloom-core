import { FolderPlus, Pencil, Tags } from 'lucide-react'
import { useState } from 'react'

import { EmptyState } from '@/components/empty-state'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Switch } from '@/components/ui/switch'
import { useDepsChanged } from '@/hooks/use-deps-changed'
import { cn } from '@/lib/utils'

import { useProductCategories, useSaveCategory } from './api'
import { CATEGORY_ICONS, palette } from './catalog-utils'
import { ColorSwatches } from './shared'
import type { CategoryInput, ProductCategory } from './types'

const EMPTY: CategoryInput = { name: '', color: 'amber', icon: 'coffee', sort_order: 0, active: true, send_to_orders: true }

function CategoryDialog({
  open,
  onOpenChange,
  category,
  nextOrder,
}: {
  open: boolean
  onOpenChange: (o: boolean) => void
  category: ProductCategory | null
  nextOrder: number
}) {
  const save = useSaveCategory()
  const [form, setForm] = useState<CategoryInput>(EMPTY)
  if (useDepsChanged([open, category, nextOrder]) && open)
    setForm(category ? { ...category } : { ...EMPTY, sort_order: nextOrder })
  const Preview = CATEGORY_ICONS[form.icon] ?? CATEGORY_ICONS.package
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{category ? 'Editar categoría' : 'Nueva categoría'}</DialogTitle>
        </DialogHeader>
        <form
          className="grid gap-4"
          onSubmit={(e) => {
            e.preventDefault()
            save.mutate(
              { id: category?.id, data: { ...form, name: form.name.trim() } },
              { onSuccess: () => onOpenChange(false) },
            )
          }}
        >
          <div className="flex items-center gap-3">
            <div className={cn('flex size-12 shrink-0 items-center justify-center rounded-2xl', palette(form.color).tile)}>
              <Preview className="size-6" />
            </div>
            <div className="grid flex-1 gap-1.5">
              <Label htmlFor="cat-name">Nombre</Label>
              <Input id="cat-name" autoFocus value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />
            </div>
          </div>
          <div className="grid gap-1.5">
            <Label>Color</Label>
            <ColorSwatches value={form.color} onChange={(color) => setForm((f) => ({ ...f, color }))} />
          </div>
          <div className="grid gap-1.5">
            <Label>Ícono</Label>
            <div className="grid grid-cols-9 gap-1.5">
              {Object.entries(CATEGORY_ICONS).map(([key, Icon]) => (
                <button
                  key={key}
                  type="button"
                  aria-label={key}
                  onClick={() => setForm((f) => ({ ...f, icon: key }))}
                  className={cn(
                    'flex aspect-square items-center justify-center rounded-lg border transition-colors',
                    form.icon === key ? 'border-primary bg-primary/10 text-primary' : 'hover:bg-muted',
                  )}
                >
                  <Icon className="size-4" />
                </button>
              ))}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-1.5">
              <Label htmlFor="cat-order">Orden en el POS</Label>
              <Input
                id="cat-order"
                type="number"
                className="tabular"
                value={form.sort_order}
                onChange={(e) => setForm((f) => ({ ...f, sort_order: Number(e.target.value) || 0 }))}
              />
            </div>
            <label className="flex items-center justify-between gap-3 self-end rounded-xl border px-3 py-2">
              <span className="text-sm font-medium">Activa</span>
              <Switch checked={form.active} onCheckedChange={(active) => setForm((f) => ({ ...f, active }))} />
            </label>
          </div>
          <label className="flex items-center justify-between gap-3 rounded-xl border px-3 py-2">
            <span>
              <span className="block text-sm font-medium">Va a la pantalla de pedidos</span>
              <span className="block text-xs text-muted-foreground">Apagalo para lo que se entrega en el mostrador (p. ej. panadería).</span>
            </span>
            <Switch
              checked={form.send_to_orders}
              onCheckedChange={(send_to_orders) => setForm((f) => ({ ...f, send_to_orders }))}
              aria-label="Va a la pantalla de pedidos"
            />
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

export function CategoriesTab() {
  const { data, isLoading } = useProductCategories()
  const [editing, setEditing] = useState<ProductCategory | null>(null)
  const [open, setOpen] = useState(false)
  const nextOrder = (data?.reduce((m, c) => Math.max(m, c.sort_order), -1) ?? -1) + 1
  const show = (c: ProductCategory | null) => {
    setEditing(c)
    setOpen(true)
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between gap-2">
        <p className="text-sm text-muted-foreground">El orden define cómo aparecen las pestañas en el punto de venta.</p>
        <Button onClick={() => show(null)}>
          <FolderPlus /> Nueva categoría
        </Button>
      </div>
      {isLoading ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-24 rounded-2xl" />
          ))}
        </div>
      ) : !data?.length ? (
        <EmptyState icon={Tags} title="Sin categorías" description="Agrupá tus productos (Cafetería, Panadería…) para encontrarlos rápido en el POS." />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {data.map((c) => {
            const Icon = CATEGORY_ICONS[c.icon] ?? CATEGORY_ICONS.package
            return (
              <Card key={c.id} className={cn('rounded-2xl', !c.active && 'opacity-60')}>
                <CardContent className="flex items-center gap-4">
                  <div className={cn('flex size-12 shrink-0 items-center justify-center rounded-2xl', palette(c.color).tile)}>
                    <Icon className="size-6" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium">{c.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {c.product_count} {c.product_count === 1 ? 'producto' : 'productos'} · orden {c.sort_order}
                    </p>
                  </div>
                  {!c.send_to_orders && <Badge variant="secondary">Sin pantalla de pedidos</Badge>}
                  {!c.active && <Badge variant="outline">Inactiva</Badge>}
                  <Button variant="ghost" size="icon" aria-label="Editar" onClick={() => show(c)}>
                    <Pencil />
                  </Button>
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}
      <CategoryDialog open={open} onOpenChange={setOpen} category={editing} nextOrder={nextOrder} />
    </div>
  )
}
