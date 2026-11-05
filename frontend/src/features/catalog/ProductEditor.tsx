import { Plus, Trash2, TrendingDown, TrendingUp } from 'lucide-react'
import { useMemo, useState } from 'react'

import { MoneyInput } from '@/components/money-input'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'
import { Sheet, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { LockedNotice } from '@/components/lock-badge'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { fmtDateTime, fmtMoney, fmtPct } from '@/lib/format'
import { cn } from '@/lib/utils'
import { useDepsChanged } from '@/hooks/use-deps-changed'

import { useStockItems } from '../stock/api'
import { StockItemPicker } from '../stock/components'
import { useDeactivateProduct, useModifierGroups, usePriceHistory, useProductCategories, useSaveProduct, useSizes } from './api'
import { marginOf, marginTextClass } from './catalog-utils'
import { MenuDetailsEditor } from './MenuDetailsEditor'
import { ColorSwatches } from './shared'
import { draftsFor, type SizeDraft, toInput } from './size-utils'
import { SizesEditor } from './SizesEditor'
import type { Product, ProductInput } from './types'
import { ProBadge } from '../license/pro-gate'
import { useHasFeature } from '../license/api'

interface DraftRecipe {
  key: string
  stock_item_id: number | null
  qty: string
}

let k = 0
const newRecipe = (p: Partial<DraftRecipe> = {}): DraftRecipe => ({ key: `r${++k}`, stock_item_id: null, qty: '', ...p })
const num = (s: string) => {
  const n = Number(s.replace(',', '.'))
  return Number.isFinite(n) ? n : 0
}

function Section({ title, description, children }: { title: string; description?: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3">
      <div>
        <h3 className="font-heading text-base font-semibold">{title}</h3>
        {description && <p className="text-xs text-muted-foreground">{description}</p>}
      </div>
      {children}
    </section>
  )
}

function PriceHistoryList({ productId }: { productId: number }) {
  const { data, isLoading } = usePriceHistory(productId)
  if (isLoading) return <p className="text-sm text-muted-foreground">Cargando…</p>
  if (!data?.length) return <p className="text-sm text-muted-foreground">Todavía no hubo cambios de precio.</p>
  return (
    <div className="space-y-1.5">
      {data.slice(0, 12).map((h) => {
        const up = h.new_cents >= h.old_cents
        return (
          <div key={h.id} className="flex items-center gap-3 rounded-lg px-2 py-1.5 text-sm hover:bg-muted/50">
            {up ? <TrendingUp className="size-4 text-destructive" /> : <TrendingDown className="size-4 text-success" />}
            <span className="tabular text-muted-foreground line-through">{fmtMoney(h.old_cents)}</span>
            <span className="tabular font-medium">{fmtMoney(h.new_cents)}</span>
            {h.size_name && <span className="text-xs text-muted-foreground">{h.size_name}</span>}
            {h.change_pct != null && (
              <span className={cn('tabular text-xs', up ? 'text-destructive' : 'text-success')}>
                {up ? '+' : ''}
                {fmtPct(h.change_pct)}
              </span>
            )}
            <span className="ml-auto text-xs text-muted-foreground">
              {fmtDateTime(h.ts)}
              {h.user_name ? ` · ${h.user_name}` : ''}
            </span>
          </div>
        )
      })}
    </div>
  )
}

export function ProductEditor({
  open,
  product,
  onOpenChange,
  defaultCategoryId,
}: {
  open: boolean
  product: Product | null
  onOpenChange: (o: boolean) => void
  defaultCategoryId?: number | null
}) {
  const cats = useProductCategories()
  const groups = useModifierGroups()
  const stock = useStockItems({ enabled: open })
  const sizesQ = useSizes()
  const save = useSaveProduct()
  const deactivate = useDeactivateProduct()

  const [name, setName] = useState('')
  const [categoryId, setCategoryId] = useState<number | null>(null)
  const [price, setPrice] = useState<number | null>(null)
  const [color, setColor] = useState<string | null>(null)
  const [description, setDescription] = useState('')
  const [active, setActive] = useState(true)
  const [showInPos, setShowInPos] = useState(true)
  const [resale, setResale] = useState(false)
  const [stockItemId, setStockItemId] = useState<number | null>(null)
  const [recipe, setRecipe] = useState<DraftRecipe[]>([])
  const [groupIds, setGroupIds] = useState<number[]>([])
  const [sized, setSized] = useState(false)
  const [sizeDrafts, setSizeDrafts] = useState<SizeDraft[]>([])
  const [defaultSize, setDefaultSize] = useState<number | null>(null)
  const [longDescription, setLongDescription] = useState('')
  const [tags, setTags] = useState<string[]>([])
  const [featured, setFeatured] = useState(false)
  const [prepMinutes, setPrepMinutes] = useState('')
  const ordersPro = useHasFeature('orders_pro')

  if (useDepsChanged([open, product, defaultCategoryId]) && open) {
    setName(product?.name ?? '')
    setCategoryId(product?.category_id ?? defaultCategoryId ?? null)
    setPrice(product?.price_cents ?? null)
    setColor(product?.color ?? null)
    setDescription(product?.description ?? '')
    setActive(product?.active ?? true)
    setShowInPos(product?.show_in_pos ?? true)
    setResale(!!product?.stock_item_id)
    setStockItemId(product?.stock_item_id ?? null)
    setRecipe(product?.recipe_items.map((r) => newRecipe({ stock_item_id: r.stock_item_id, qty: String(r.qty) })) ?? [])
    setGroupIds(product?.modifier_group_ids ?? [])
    setSized(!!product?.sizes.length)
    setSizeDrafts(draftsFor(sizesQ.data ?? [], product))
    setDefaultSize(product?.sizes.find((s) => s.is_default)?.size_id ?? null)
    setLongDescription(product?.long_description ?? '')
    setTags(product?.tags ?? [])
    setFeatured(product?.featured ?? false)
    setPrepMinutes(product?.prep_minutes ? String(product.prep_minutes) : '')
  }
  // Sizes may load after the editor opened (or a size was created meanwhile): rebuild untouched rows.
  if (useDepsChanged([sizesQ.data]) && open && sizesQ.data && !sizeDrafts.some((d) => d.enabled)) {
    setSizeDrafts(draftsFor(sizesQ.data, product))
  }

  const byId = useMemo(() => new Map(stock.data?.map((s) => [s.id, s])), [stock.data])
  const directCost = resale && stockItemId ? (byId.get(stockItemId)?.avg_cost_cents ?? 0) : 0
  const lineCosts = recipe.map((r) => (r.stock_item_id ? num(r.qty) * (byId.get(r.stock_item_id)?.avg_cost_cents ?? 0) : 0))
  const cost = Math.round(directCost + lineCosts.reduce((a, b) => a + b, 0))
  const margin = marginOf(price ?? 0, cost)
  const updateRecipe = (key: string, patch: Partial<DraftRecipe>) =>
    setRecipe((rs) => rs.map((r) => (r.key === key ? { ...r, ...patch } : r)))

  const baseRecipe = useMemo(() => {
    const m = new Map<number, number>()
    if (resale && stockItemId) m.set(stockItemId, 1)
    for (const r of recipe) if (r.stock_item_id && num(r.qty) > 0) m.set(r.stock_item_id, (m.get(r.stock_item_id) ?? 0) + num(r.qty))
    return m
  }, [resale, stockItemId, recipe])
  const enabledSizes = sizeDrafts.filter((d) => d.enabled)
  const effectiveDefault = enabledSizes.some((d) => d.size_id === defaultSize) ? defaultSize : (enabledSizes[0]?.size_id ?? null)
  const sizesValid = !sized || (enabledSizes.length > 0 && enabledSizes.every((d) => d.price != null && d.price >= 0))

  const prep = prepMinutes.trim() ? Math.round(Number(prepMinutes)) : null
  const prepValid = prep == null || (Number.isFinite(prep) && prep >= 1 && prep <= 240)
  const valid = prepValid && name.trim() && (sized || (price != null && price >= 0)) && (!resale || stockItemId) && sizesValid

  const submit = () => {
    if (!valid) return
    const data: ProductInput = {
      name: name.trim(),
      category_id: categoryId,
      description: description.trim() || null,
      price_cents: sized ? (enabledSizes.find((d) => d.size_id === effectiveDefault)?.price ?? 0) : (price ?? 0),
      color,
      active,
      show_in_pos: showInPos,
      stock_item_id: resale ? stockItemId : null,
      sort_order: product?.sort_order ?? 0,
      recipe_items: recipe
        .filter((r) => r.stock_item_id && num(r.qty) > 0)
        .map((r) => ({ stock_item_id: r.stock_item_id!, qty: num(r.qty) })),
      modifier_group_ids: groupIds,
      long_description: longDescription.trim() || null,
      tags,
      featured,
      prep_minutes: prep,
      sizes: sized ? toInput(sizeDrafts, effectiveDefault) : [],
    }
    save.mutate({ id: product?.id, data }, { onSuccess: () => onOpenChange(false) })
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full gap-0 sm:max-w-2xl data-[side=right]:sm:max-w-2xl">
        <SheetHeader className="border-b">
          <SheetTitle className="font-heading text-xl">{product ? product.name : 'Nuevo producto'}</SheetTitle>
          <SheetDescription>Precio, receta, tamaños y modificadores. El costo y el margen se calculan en vivo.</SheetDescription>
        </SheetHeader>

        <ScrollArea className="min-h-0 flex-1">
          <div className="space-y-7 p-5">
            {product?.locked && <LockedNotice what="Este producto" />}
            <Section title="Datos básicos">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="grid gap-1.5 sm:col-span-2">
                  <Label htmlFor="pe-name">Nombre</Label>
                  <Input id="pe-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Ej.: Latte" />
                </div>
                <div className="grid gap-1.5">
                  <Label htmlFor="pe-cat">Categoría</Label>
                  <Select value={categoryId ? String(categoryId) : 'none'} onValueChange={(v) => setCategoryId(v === 'none' ? null : Number(v))}>
                    <SelectTrigger id="pe-cat" className="w-full">
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
                  <Label htmlFor="pe-price">Precio de venta</Label>
                  {sized ? (
                    <p className="flex h-9 items-center rounded-md border border-dashed px-3 text-sm text-muted-foreground">Se define por tamaño</p>
                  ) : (
                    <MoneyInput id="pe-price" value={price} onChange={setPrice} className="[&_input]:text-base [&_input]:font-semibold" />
                  )}
                </div>
                <div className="grid gap-1.5 sm:col-span-2">
                  <Label>Color en el POS</Label>
                  <ColorSwatches value={color} onChange={setColor} />
                </div>
                <div className="grid gap-1.5 sm:col-span-2">
                  <Label htmlFor="pe-desc">Descripción corta (opcional)</Label>
                  <Textarea id="pe-desc" rows={2} value={description} onChange={(e) => setDescription(e.target.value)} />
                </div>
                <label className="flex items-center justify-between gap-3 rounded-xl border px-3 py-2.5">
                  <span className="text-sm font-medium">Activo</span>
                  <Switch checked={active} onCheckedChange={setActive} />
                </label>
                <label className="flex items-center justify-between gap-3 rounded-xl border px-3 py-2.5">
                  <span className="text-sm font-medium">Visible en el POS</span>
                  <Switch checked={showInPos} onCheckedChange={setShowInPos} />
                </label>
              </div>
            </Section>

            <Separator />

            <Section
              title="Receta / escandallo"
              description={
                sized
                  ? 'Receta base (factor ×1). Cada tamaño la escala y puede ajustar insumos.'
                  : 'Insumos que se descuentan del stock por cada unidad vendida.'
              }
            >
              <label className="flex items-center justify-between gap-3 rounded-xl border px-3 py-2.5">
                <span>
                  <span className="block text-sm font-medium">Producto de reventa</span>
                  <span className="block text-xs text-muted-foreground">Se vende tal cual se compra (ej.: medialuna) y descuenta 1 unidad del insumo.</span>
                </span>
                <Switch checked={resale} onCheckedChange={setResale} />
              </label>
              {resale && (
                <div className="grid gap-1.5">
                  <Label>Insumo que se vende</Label>
                  <StockItemPicker items={stock.data} value={stockItemId} onChange={(i) => setStockItemId(i.id)} />
                </div>
              )}

              <div className="space-y-2">
                {recipe.map((r, idx) => {
                  const item = r.stock_item_id ? byId.get(r.stock_item_id) : undefined
                  return (
                    <div key={r.key} className="grid grid-cols-[minmax(0,1fr)_7rem_6rem_2.25rem] items-center gap-2">
                      <StockItemPicker
                        items={stock.data}
                        value={r.stock_item_id}
                        excludeIds={recipe.map((x) => x.stock_item_id).filter((x): x is number => x != null)}
                        onChange={(i) => updateRecipe(r.key, { stock_item_id: i.id })}
                      />
                      <div className="relative">
                        <Input
                          inputMode="decimal"
                          className="tabular h-9 pr-8"
                          placeholder="0"
                          value={r.qty}
                          onChange={(e) => updateRecipe(r.key, { qty: e.target.value })}
                        />
                        <span className="pointer-events-none absolute top-1/2 right-2.5 -translate-y-1/2 text-xs text-muted-foreground">
                          {item?.unit ?? ''}
                        </span>
                      </div>
                      <span className="tabular text-right text-sm">{fmtMoney(Math.round(lineCosts[idx]))}</span>
                      <Button variant="ghost" size="icon" aria-label="Quitar insumo" onClick={() => setRecipe((rs) => rs.filter((x) => x.key !== r.key))}>
                        <Trash2 className="text-muted-foreground" />
                      </Button>
                    </div>
                  )
                })}
                <Button variant="outline" size="sm" onClick={() => setRecipe((rs) => [...rs, newRecipe()])}>
                  <Plus /> Agregar insumo
                </Button>
              </div>

              {!sized && (
              <div className="grid grid-cols-3 gap-2 rounded-2xl bg-muted/60 p-4">
                <div>
                  <p className="text-xs text-muted-foreground">Costo</p>
                  <p className="tabular text-lg font-semibold">{fmtMoney(cost)}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Ganancia bruta</p>
                  <p className="tabular text-lg font-semibold">{price != null ? fmtMoney(price - cost) : '—'}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Margen</p>
                  <p className={cn('tabular text-lg font-semibold', marginTextClass(margin))}>{fmtPct(margin)}</p>
                </div>
                {margin != null && margin < 55 && (
                  <p className="col-span-3 text-xs text-muted-foreground">
                    Para un margen del 65% el precio debería rondar {fmtMoney(Math.ceil(cost / 0.35 / 5000) * 5000)}.
                  </p>
                )}
              </div>
              )}
            </Section>

            <Separator />

            <Section title="Tamaños" description="Vendé el producto en distintos tamaños, cada uno con su precio y su receta.">
              <label className="flex items-center justify-between gap-3 rounded-xl border px-3 py-2.5">
                <span>
                  <span className="block text-sm font-medium">Se vende en distintos tamaños</span>
                  <span className="block text-xs text-muted-foreground">En el POS se elige el tamaño al agregarlo (con uno predeterminado).</span>
                </span>
                <Switch checked={sized} onCheckedChange={setSized} aria-label="Se vende en distintos tamaños" />
              </label>
              {sized && (
                <SizesEditor
                  sizes={sizesQ.data ?? []}
                  drafts={sizeDrafts}
                  onChange={setSizeDrafts}
                  defaultId={effectiveDefault}
                  onDefault={setDefaultSize}
                  base={baseRecipe}
                  stock={stock.data}
                />
              )}
              {sized && !sizesValid && <p className="text-xs text-destructive">Elegí al menos un tamaño y poné el precio de cada uno.</p>}
            </Section>

            <Separator />

            <Section title="Pantalla de pedidos" description="Tiempo objetivo de preparación: si se pasa, el pedido se marca atrasado.">
              <div className="flex flex-wrap items-end gap-3">
                <div className="grid gap-1.5">
                  <Label htmlFor="prod-prep" className="flex items-center gap-2">
                    Minutos de preparación {ordersPro === false && <ProBadge />}
                  </Label>
                  <Input
                    id="prod-prep"
                    inputMode="numeric"
                    className="tabular h-9 w-32"
                    placeholder="Del canal"
                    value={prepMinutes}
                    disabled={ordersPro === false}
                    onChange={(e) => setPrepMinutes(e.target.value.replace(/[^0-9]/g, ''))}
                  />
                </div>
                <p className="max-w-sm text-xs text-muted-foreground">
                  {ordersPro === false
                    ? 'Con Pedidos avanzados cada producto tiene su tiempo; si no, se usa el tiempo del canal.'
                    : 'Vacío = el tiempo del canal (salón, para llevar, delivery). El pedido toma el mayor de sus productos.'}
                </p>
              </div>
              {!prepValid && <p className="text-xs text-destructive">Entre 1 y 240 minutos.</p>}
            </Section>

            <Separator />

            <Section title="Menú para clientes" description="Lo que ven tus clientes al tocar el producto en el menú del QR.">
              <MenuDetailsEditor
                product={product}
                longDescription={longDescription}
                onLongDescription={setLongDescription}
                tags={tags}
                onTags={setTags}
                featured={featured}
                onFeatured={setFeatured}
              />
            </Section>

            <Separator />

            <Section title="Modificadores" description="Opciones que el cajero puede elegir al vender (leche, extras…).">
              {groups.data?.length ? (
                <div className="grid gap-2 sm:grid-cols-2">
                  {groups.data.map((g) => {
                    const checked = groupIds.includes(g.id)
                    return (
                      <label
                        key={g.id}
                        className={cn(
                          'flex cursor-pointer items-start gap-3 rounded-xl border p-3 transition-colors',
                          checked ? 'border-primary bg-primary/5' : 'hover:bg-muted/50',
                        )}
                      >
                        <Checkbox
                          checked={checked}
                          onCheckedChange={(v) => setGroupIds((ids) => (v ? [...ids, g.id] : ids.filter((x) => x !== g.id)))}
                        />
                        <span className="min-w-0">
                          <span className="block text-sm font-medium">{g.name}</span>
                          <span className="block truncate text-xs text-muted-foreground">
                            {g.modifiers.map((m) => m.name).join(', ') || 'Sin opciones'}
                          </span>
                        </span>
                      </label>
                    )
                  })}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">No hay grupos de modificadores. Crealos en la pestaña Modificadores.</p>
              )}
            </Section>

            {product && (
              <>
                <Separator />
                <Section title="Historial de precios" description={`Precio actual: ${fmtMoney(product.price_cents)}`}>
                  <PriceHistoryList productId={product.id} />
                </Section>
              </>
            )}
          </div>
        </ScrollArea>

        <SheetFooter className="flex-row justify-between border-t">
          {product?.active ? (
            <Button
              variant="ghost"
              className="text-destructive"
              onClick={() => deactivate.mutate(product.id, { onSuccess: () => onOpenChange(false) })}
            >
              <Trash2 /> Desactivar
            </Button>
          ) : (
            <span />
          )}
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              Cancelar
            </Button>
            <Button disabled={!valid || save.isPending || !!product?.locked} onClick={submit}>
              Guardar
            </Button>
          </div>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}
