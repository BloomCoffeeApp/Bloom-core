import { LayoutGrid, List, Package, Plus, TrendingUp } from 'lucide-react'
import { useMemo, useState } from 'react'

import { type ColumnDef, DataTable } from '@/components/data-table'
import { EmptyState } from '@/components/empty-state'
import { StatCard } from '@/components/stat-card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { Switch } from '@/components/ui/switch'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { fmtMoney, fmtPct } from '@/lib/format'
import { cn } from '@/lib/utils'

import { useProductCategories, useProducts } from './api'
import { BulkPriceDialog } from './BulkPriceDialog'
import { ProductEditor } from './ProductEditor'
import { categoryIcon, marginTextClass, palette } from './catalog-utils'
import { CategoryChip, MarginBadge } from './shared'
import type { Product } from './types'

export function ProductsTab() {
  const [includeInactive, setIncludeInactive] = useState(false)
  const products = useProducts(includeInactive)
  const cats = useProductCategories()
  const [category, setCategory] = useState<number | 'all'>('all')
  const [view, setView] = useState<'table' | 'grid'>('table')
  const [search, setSearch] = useState('')
  const [editing, setEditing] = useState<Product | null>(null)
  const [editorOpen, setEditorOpen] = useState(false)
  const [bulkOpen, setBulkOpen] = useState(false)

  const filtered = useMemo(
    () =>
      (products.data ?? []).filter(
        (p) =>
          (category === 'all' || p.category_id === category) &&
          (view === 'table' || !search || p.name.toLowerCase().includes(search.toLowerCase())),
      ),
    [products.data, category, search, view],
  )

  const stats = useMemo(() => {
    const list = (products.data ?? []).filter((p) => p.active && p.margin_pct != null)
    const avg = list.length ? list.reduce((a, p) => a + (p.margin_pct ?? 0), 0) / list.length : null
    return { avg, low: list.filter((p) => (p.margin_pct ?? 0) < 55).length, count: products.data?.filter((p) => p.active).length ?? 0 }
  }, [products.data])

  const open = (p: Product | null) => {
    setEditing(p)
    setEditorOpen(true)
  }

  const columns = useMemo<ColumnDef<Product, unknown>[]>(
    () => [
      {
        accessorKey: 'name',
        header: 'Producto',
        cell: ({ row }) => (
          <div className="flex items-center gap-3">
            <span className={cn('size-2.5 shrink-0 rounded-full', palette(row.original.color ?? row.original.category?.color).dot)} />
            <div className="min-w-0">
              <p className={cn('truncate font-medium', !row.original.active && 'text-muted-foreground line-through')}>{row.original.name}</p>
              <p className="truncate text-xs text-muted-foreground">
                {row.original.stock_item_id
                  ? `Reventa · ${row.original.stock_item_name}`
                  : `${row.original.recipe_items.length} insumos`}
                {!row.original.show_in_pos && ' · oculto en POS'}
              </p>
            </div>
          </div>
        ),
      },
      {
        id: 'category',
        header: 'Categoría',
        accessorFn: (p) => p.category?.name ?? '',
        cell: ({ row }) => <CategoryChip category={row.original.category} />,
      },
      {
        accessorKey: 'price_cents',
        header: 'Precio',
        cell: ({ row }) => <span className="tabular font-semibold">{fmtMoney(row.original.price_cents)}</span>,
      },
      {
        accessorKey: 'cost_cents',
        header: 'Costo',
        cell: ({ row }) => <span className="tabular text-muted-foreground">{fmtMoney(row.original.cost_cents)}</span>,
      },
      {
        accessorKey: 'margin_pct',
        header: 'Margen',
        cell: ({ row }) => <MarginBadge margin={row.original.margin_pct} />,
      },
      {
        id: 'mods',
        header: 'Modif.',
        accessorFn: (p) => p.modifier_group_ids.length,
        cell: ({ row }) =>
          row.original.modifier_group_ids.length ? (
            <Badge variant="outline">{row.original.modifier_group_ids.length}</Badge>
          ) : (
            <span className="text-muted-foreground">—</span>
          ),
      },
    ],
    [],
  )

  const toolbarRight = (
    <div className="ml-auto flex items-center gap-2">
      <label className="flex items-center gap-2 text-sm text-muted-foreground">
        <Switch checked={includeInactive} onCheckedChange={setIncludeInactive} /> Inactivos
      </label>
      <ToggleGroup type="single" variant="outline" value={view} onValueChange={(v) => v && setView(v as 'table' | 'grid')}>
        <ToggleGroupItem value="table" aria-label="Ver como tabla">
          <List />
        </ToggleGroupItem>
        <ToggleGroupItem value="grid" aria-label="Ver como grilla">
          <LayoutGrid />
        </ToggleGroupItem>
      </ToggleGroup>
      <Button variant="outline" onClick={() => setBulkOpen(true)}>
        <TrendingUp /> Aumento masivo
      </Button>
      <Button onClick={() => open(null)}>
        <Plus /> Nuevo producto
      </Button>
    </div>
  )

  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard label="Productos activos" value={stats.count} icon={Package} loading={products.isLoading} />
        <StatCard
          label="Margen promedio"
          value={<span className={marginTextClass(stats.avg)}>{fmtPct(stats.avg)}</span>}
          icon={TrendingUp}
          loading={products.isLoading}
        />
        <StatCard
          label="Con margen bajo (<55%)"
          value={stats.low}
          tone={stats.low ? 'warning' : 'success'}
          hint={stats.low ? 'Revisá precios o recetas' : '¡Bien ahí!'}
          loading={products.isLoading}
        />
      </div>

      <div className="flex flex-wrap gap-1.5">
        <button
          onClick={() => setCategory('all')}
          className={cn(
            'rounded-full border px-3 py-1 text-sm transition-colors',
            category === 'all' ? 'border-primary bg-primary text-primary-foreground' : 'hover:bg-muted',
          )}
        >
          Todas
        </button>
        {cats.data
          ?.filter((c) => c.active)
          .map((c) => {
            const Icon = categoryIcon(c.icon)
            const active = category === c.id
            return (
              <button
                key={c.id}
                onClick={() => setCategory(c.id)}
                className={cn(
                  'inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-sm transition-colors',
                  active ? cn('border-transparent', palette(c.color).chip, 'ring-2 ring-primary/40') : 'hover:bg-muted',
                )}
              >
                <Icon className="size-3.5" /> {c.name}
                <span className="tabular text-xs opacity-60">{c.product_count}</span>
              </button>
            )
          })}
      </div>

      {view === 'table' ? (
        <DataTable
          columns={columns}
          data={filtered}
          loading={products.isLoading}
          onRowClick={open}
          searchPlaceholder="Buscar producto…"
          emptyTitle="No hay productos"
          emptyDescription="Creá tu primer producto con su receta."
          toolbar={toolbarRight}
        />
      ) : (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <Input className="max-w-xs" placeholder="Buscar producto…" value={search} onChange={(e) => setSearch(e.target.value)} />
            {toolbarRight}
          </div>
          {products.isLoading ? (
            <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-4">
              {Array.from({ length: 8 }).map((_, i) => (
                <Skeleton key={i} className="h-36 rounded-2xl" />
              ))}
            </div>
          ) : !filtered.length ? (
            <EmptyState icon={Package} title="No hay productos" />
          ) : (
            <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-4">
              {filtered.map((p) => {
                const Icon = categoryIcon(p.category?.icon)
                return (
                  <Card
                    key={p.id}
                    role="button"
                    tabIndex={0}
                    onClick={() => open(p)}
                    onKeyDown={(e) => e.key === 'Enter' && open(p)}
                    className={cn(
                      'cursor-pointer gap-3 rounded-2xl p-4 transition-all hover:-translate-y-0.5 hover:shadow-md',
                      !p.active && 'opacity-60',
                    )}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className={cn('flex size-10 items-center justify-center rounded-xl', palette(p.color ?? p.category?.color).tile)}>
                        <Icon className="size-5" />
                      </div>
                      <MarginBadge margin={p.margin_pct} />
                    </div>
                    <div className="min-w-0">
                      <p className="truncate font-medium">{p.name}</p>
                      <p className="truncate text-xs text-muted-foreground">{p.category?.name ?? 'Sin categoría'}</p>
                    </div>
                    <div className="flex items-end justify-between">
                      <span className="tabular text-lg font-semibold">{fmtMoney(p.price_cents)}</span>
                      <span className="tabular text-xs text-muted-foreground">costo {fmtMoney(p.cost_cents)}</span>
                    </div>
                  </Card>
                )
              })}
            </div>
          )}
        </div>
      )}

      <ProductEditor
        open={editorOpen}
        product={editing}
        onOpenChange={setEditorOpen}
        defaultCategoryId={category === 'all' ? null : category}
      />
      <BulkPriceDialog open={bulkOpen} onOpenChange={setBulkOpen} />
    </div>
  )
}
