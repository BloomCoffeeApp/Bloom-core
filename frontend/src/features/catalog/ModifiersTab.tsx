import { ChevronDown, Layers, Pencil, Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'

import { ConfirmDialog } from '@/components/confirm-dialog'
import { EmptyState } from '@/components/empty-state'
import { MoneyInput } from '@/components/money-input'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { fmtMoney, fmtNumber } from '@/lib/format'
import { useDepsChanged } from '@/hooks/use-deps-changed'

import { useStockItems } from '../stock/api'
import { StockItemPicker } from '../stock/components'
import { useDeleteGroup, useModifierGroups, useProducts, useSaveGroup } from './api'
import type { ModifierGroup } from './types'

interface DraftMod {
  key: string
  id: number | null
  name: string
  price: number | null
  recipe: { key: string; stock_item_id: number | null; qty: string }[]
}

let seq = 0
const key = () => `m${++seq}`
const num = (s: string) => {
  const n = Number(s.replace(',', '.'))
  return Number.isFinite(n) ? n : 0
}

function GroupDialog({ open, onOpenChange, group }: { open: boolean; onOpenChange: (o: boolean) => void; group: ModifierGroup | null }) {
  const save = useSaveGroup()
  const stock = useStockItems({ enabled: open })
  const [name, setName] = useState('')
  const [min, setMin] = useState('0')
  const [max, setMax] = useState('1')
  const [mods, setMods] = useState<DraftMod[]>([])

  if (useDepsChanged([open, group]) && open) {
    setName(group?.name ?? '')
    setMin(String(group?.min_select ?? 0))
    setMax(String(group?.max_select ?? 1))
    setMods(
      group?.modifiers.map((m) => ({
        key: key(),
        id: m.id,
        name: m.name,
        price: m.price_delta_cents,
        recipe: m.recipe_items.map((r) => ({ key: key(), stock_item_id: r.stock_item_id, qty: String(r.qty_delta) })),
      })) ?? [{ key: key(), id: null, name: '', price: 0, recipe: [] }],
    )
  }

  const upd = (k: string, patch: Partial<DraftMod>) => setMods((ms) => ms.map((m) => (m.key === k ? { ...m, ...patch } : m)))
  const minN = Number(min) || 0
  const maxN = Number(max) || 1
  const valid = name.trim() && minN <= maxN && mods.every((m) => m.name.trim())
  const unitOf = (id: number | null) => stock.data?.find((s) => s.id === id)?.unit ?? ''

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle className="font-heading text-xl">{group ? 'Editar grupo' : 'Nuevo grupo de modificadores'}</DialogTitle>
          <DialogDescription>Ej.: “Tipo de leche” (elegir 1) o “Extras” (hasta 3).</DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 sm:grid-cols-[1fr_7rem_7rem]">
          <div className="grid gap-1.5">
            <Label htmlFor="g-name">Nombre</Label>
            <Input id="g-name" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="g-min">Mínimo</Label>
            <Input id="g-min" type="number" min={0} className="tabular" value={min} onChange={(e) => setMin(e.target.value)} />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="g-max">Máximo</Label>
            <Input id="g-max" type="number" min={1} className="tabular" value={max} onChange={(e) => setMax(e.target.value)} />
          </div>
        </div>
        {minN > maxN && <p className="text-xs text-destructive">El mínimo no puede superar al máximo.</p>}

        <div className="space-y-2">
          <Label>Opciones</Label>
          {mods.map((m) => (
            <Collapsible key={m.key} className="rounded-xl border">
              <div className="grid grid-cols-[minmax(0,1fr)_9rem_auto_2.25rem] items-center gap-2 p-2">
                <Input placeholder="Nombre de la opción" value={m.name} onChange={(e) => upd(m.key, { name: e.target.value })} />
                <MoneyInput value={m.price} onChange={(c) => upd(m.key, { price: c })} placeholder="0" />
                <CollapsibleTrigger asChild>
                  <Button variant="ghost" size="sm" className="text-xs">
                    Stock {m.recipe.length ? <Badge variant="secondary">{m.recipe.length}</Badge> : null}
                    <ChevronDown />
                  </Button>
                </CollapsibleTrigger>
                <Button variant="ghost" size="icon" aria-label="Quitar opción" onClick={() => setMods((ms) => ms.filter((x) => x.key !== m.key))}>
                  <Trash2 className="text-muted-foreground" />
                </Button>
              </div>
              <CollapsibleContent className="space-y-2 border-t bg-muted/30 p-3">
                <p className="text-xs text-muted-foreground">
                  Impacto en el stock al elegir esta opción. Usá negativo para consumir menos (ej.: avena: −200 ml leche, +200 ml avena).
                </p>
                {m.recipe.map((r) => (
                  <div key={r.key} className="grid grid-cols-[minmax(0,1fr)_7rem_2.25rem] items-center gap-2">
                    <StockItemPicker
                      items={stock.data}
                      value={r.stock_item_id}
                      onChange={(it) =>
                        upd(m.key, { recipe: m.recipe.map((x) => (x.key === r.key ? { ...x, stock_item_id: it.id } : x)) })
                      }
                    />
                    <div className="relative">
                      <Input
                        inputMode="decimal"
                        className="tabular h-9 pr-8"
                        value={r.qty}
                        onChange={(e) =>
                          upd(m.key, { recipe: m.recipe.map((x) => (x.key === r.key ? { ...x, qty: e.target.value } : x)) })
                        }
                      />
                      <span className="pointer-events-none absolute top-1/2 right-2.5 -translate-y-1/2 text-xs text-muted-foreground">
                        {unitOf(r.stock_item_id)}
                      </span>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label="Quitar"
                      onClick={() => upd(m.key, { recipe: m.recipe.filter((x) => x.key !== r.key) })}
                    >
                      <Trash2 className="text-muted-foreground" />
                    </Button>
                  </div>
                ))}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => upd(m.key, { recipe: [...m.recipe, { key: key(), stock_item_id: null, qty: '' }] })}
                >
                  <Plus /> Insumo
                </Button>
              </CollapsibleContent>
            </Collapsible>
          ))}
          <Button
            variant="outline"
            size="sm"
            onClick={() => setMods((ms) => [...ms, { key: key(), id: null, name: '', price: 0, recipe: [] }])}
          >
            <Plus /> Agregar opción
          </Button>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button
            disabled={!valid || save.isPending}
            onClick={() =>
              save.mutate(
                {
                  id: group?.id,
                  data: {
                    name: name.trim(),
                    min_select: minN,
                    max_select: maxN,
                    modifiers: mods.map((m, i) => ({
                      id: m.id,
                      name: m.name.trim(),
                      price_delta_cents: m.price ?? 0,
                      sort_order: i,
                      recipe_items: m.recipe
                        .filter((r) => r.stock_item_id && num(r.qty) !== 0)
                        .map((r) => ({ stock_item_id: r.stock_item_id!, qty_delta: num(r.qty) })),
                    })),
                  },
                },
                { onSuccess: () => onOpenChange(false) },
              )
            }
          >
            Guardar grupo
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

const selectionLabel = (g: ModifierGroup) =>
  g.min_select === 0
    ? g.max_select === 1
      ? 'Opcional · elegir 1'
      : `Opcional · hasta ${g.max_select}`
    : g.min_select === g.max_select
      ? `Obligatorio · elegir ${g.min_select}`
      : `Elegir de ${g.min_select} a ${g.max_select}`

export function ModifiersTab() {
  const { data, isLoading } = useModifierGroups()
  const products = useProducts()
  const del = useDeleteGroup()
  const [editing, setEditing] = useState<ModifierGroup | null>(null)
  const [open, setOpen] = useState(false)
  const [deleting, setDeleting] = useState<ModifierGroup | null>(null)
  const productName = (id: number) => products.data?.find((p) => p.id === id)?.name

  return (
    <div className="space-y-4">
      <div className="flex justify-between gap-2">
        <p className="text-sm text-muted-foreground">Asigná los grupos a cada producto desde su ficha.</p>
        <Button
          onClick={() => {
            setEditing(null)
            setOpen(true)
          }}
        >
          <Plus /> Nuevo grupo
        </Button>
      </div>
      {isLoading ? (
        <div className="grid gap-4 md:grid-cols-2">
          {Array.from({ length: 2 }).map((_, i) => (
            <Skeleton key={i} className="h-48 rounded-2xl" />
          ))}
        </div>
      ) : !data?.length ? (
        <EmptyState icon={Layers} title="Sin modificadores" description="Creá grupos como “Tipo de leche” o “Extras” para personalizar los pedidos." />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {data.map((g) => (
            <Card key={g.id} className="rounded-2xl">
              <CardHeader>
                <CardTitle>{g.name}</CardTitle>
                <CardDescription>{selectionLabel(g)}</CardDescription>
                <CardAction className="flex gap-1">
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label="Editar"
                    onClick={() => {
                      setEditing(g)
                      setOpen(true)
                    }}
                  >
                    <Pencil />
                  </Button>
                  <Button variant="ghost" size="icon" aria-label="Eliminar" onClick={() => setDeleting(g)}>
                    <Trash2 className="text-destructive" />
                  </Button>
                </CardAction>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="divide-y rounded-xl border">
                  {g.modifiers.map((m) => (
                    <div key={m.id} className="flex items-center justify-between gap-3 px-3 py-2 text-sm">
                      <div className="min-w-0">
                        <p className="truncate font-medium">{m.name}</p>
                        {m.recipe_items.length > 0 && (
                          <p className="truncate text-xs text-muted-foreground">
                            {m.recipe_items
                              .map((r) => `${r.qty_delta > 0 ? '+' : ''}${fmtNumber(r.qty_delta)} ${r.unit} ${r.stock_item_name}`)
                              .join(' · ')}
                          </p>
                        )}
                      </div>
                      <span className="tabular shrink-0 text-muted-foreground">
                        {m.price_delta_cents ? `${m.price_delta_cents > 0 ? '+' : ''}${fmtMoney(m.price_delta_cents)}` : 'Sin cargo'}
                      </span>
                    </div>
                  ))}
                </div>
                <p className="text-xs text-muted-foreground">
                  {g.product_ids.length
                    ? `En ${g.product_ids.length} productos: ${g.product_ids
                        .map(productName)
                        .filter(Boolean)
                        .slice(0, 5)
                        .join(', ')}${g.product_ids.length > 5 ? '…' : ''}`
                    : 'No está asignado a ningún producto.'}
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
      <GroupDialog open={open} onOpenChange={setOpen} group={editing} />
      <ConfirmDialog
        open={!!deleting}
        onOpenChange={(o) => !o && setDeleting(null)}
        title="¿Eliminar grupo?"
        description={`Se quita “${deleting?.name}” de todos los productos. Las ventas pasadas no se modifican.`}
        confirmLabel="Eliminar"
        destructive
        onConfirm={() => deleting && del.mutate(deleting.id, { onSuccess: () => setDeleting(null) })}
      />
    </div>
  )
}
