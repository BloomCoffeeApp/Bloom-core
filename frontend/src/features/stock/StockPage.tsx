import {
  AlertTriangle,
  Boxes,
  ClipboardList,
  History,
  MoreHorizontal,
  PackageX,
  Pencil,
  Plus,
  ShoppingCart,
  SlidersHorizontal,
  Trash2,
  Wallet,
} from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router'

import { ConfirmDialog } from '@/components/confirm-dialog'
import { type ColumnDef, DataTable } from '@/components/data-table'
import { PageHeader } from '@/components/page-header'
import { StatCard } from '@/components/stat-card'
import { LockBadge } from '@/components/lock-badge'
import { FreeLocksBanner } from '@/features/license/free-locks-banner'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useAuth } from '@/lib/auth'
import { fmtDate, fmtMoney, fmtQty } from '@/lib/format'

import { DiscardDialog, PackagesDialog } from './discard'

import { useDeactivateStockItem, useStockCategories, useStockItems, useStockSummary } from './api'
import {
  AdjustDialog,
  LevelBar,
  MovementsSheet,
  StatusBadge,
  StockItemDialog,
} from './components'
import { bulkCost, bulkUnit, fmtPackages } from './stock-utils'
import type { StockItem, StockStatus } from './types'

type StatusFilter = 'all' | StockStatus

export function StockPage() {
  const { can } = useAuth()
  const canEdit = can('stock.edit')
  const items = useStockItems()
  const summary = useStockSummary()
  const cats = useStockCategories()
  const [category, setCategory] = useState('all')
  const [status, setStatus] = useState<StatusFilter>('all')
  const [adjusting, setAdjusting] = useState<StockItem | null>(null)
  const [wasting, setWasting] = useState<StockItem | null>(null)
  const [packing, setPacking] = useState<StockItem | null>(null)
  const canAdjust = can('stock.adjust')
  const [viewing, setViewing] = useState<StockItem | null>(null)
  const [editing, setEditing] = useState<StockItem | null>(null)
  const [formOpen, setFormOpen] = useState(false)
  const [deleting, setDeleting] = useState<StockItem | null>(null)
  const deactivate = useDeactivateStockItem()

  const filtered = useMemo(
    () =>
      (items.data ?? []).filter(
        (i) => (category === 'all' || String(i.category_id) === category) && (status === 'all' || i.status === status),
      ),
    [items.data, category, status],
  )

  const columns = useMemo<ColumnDef<StockItem, unknown>[]>(
    () => [
      {
        accessorKey: 'name',
        header: 'Insumo',
        cell: ({ row }) => (
          <div className="min-w-0">
            <p className="flex items-center gap-2 font-medium">
              <span className="truncate">{row.original.name}</span>
              {row.original.locked && <LockBadge />}
            </p>
            <p className="truncate text-xs text-muted-foreground">
              {row.original.category_name ?? 'Sin categoría'}
              {row.original.supplier_name ? ` · ${row.original.supplier_name}` : ''}
            </p>
          </div>
        ),
      },
      {
        accessorKey: 'status',
        header: 'Estado',
        sortingFn: (a, b) => ['out', 'low', 'ok'].indexOf(a.original.status) - ['out', 'low', 'ok'].indexOf(b.original.status),
        cell: ({ row }) => <StatusBadge status={row.original.status} />,
      },
      {
        accessorKey: 'current_qty',
        header: 'Stock',
        cell: ({ row }) => (
          <div className="w-40 space-y-1.5">
            <div className="flex items-baseline justify-between gap-2 text-sm">
              <span className="tabular font-medium">{fmtQty(row.original.current_qty, row.original.unit)}</span>
              <span className="tabular text-xs text-muted-foreground">mín {fmtQty(row.original.min_qty, row.original.unit)}</span>
            </div>
            {row.original.packages.length > 0 && row.original.current_qty > 0 && (
              <div className="tabular truncate text-xs text-muted-foreground" data-testid="stock-packages">
                {fmtPackages(row.original.current_qty, row.original.unit, row.original.packages)}
              </div>
            )}
            <LevelBar item={row.original} />
          </div>
        ),
      },
      {
        accessorKey: 'avg_cost_cents',
        header: 'Costo prom.',
        cell: ({ row }) => (
          <span className="tabular text-sm">
            {fmtMoney(bulkCost(row.original.avg_cost_cents, row.original.unit))}
            <span className="text-xs text-muted-foreground"> /{bulkUnit(row.original.unit)}</span>
          </span>
        ),
      },
      {
        accessorKey: 'value_cents',
        header: 'Valorizado',
        cell: ({ row }) => <span className="tabular font-medium">{fmtMoney(row.original.value_cents)}</span>,
      },
      {
        accessorKey: 'next_expiry',
        header: 'Vence',
        cell: ({ row }) =>
          row.original.next_expiry ? (
            <span className="tabular text-sm">{fmtDate(row.original.next_expiry)}</span>
          ) : (
            <span className="text-muted-foreground">—</span>
          ),
      },
      {
        id: 'actions',
        header: '',
        enableSorting: false,
        cell: ({ row }) => (
          <div className="flex justify-end gap-1" onClick={(e) => e.stopPropagation()}>
            {canAdjust && row.original.active && !row.original.locked && (
              <Button variant="ghost" size="sm" className="text-destructive" onClick={() => setWasting(row.original)} aria-label={`Descartar ${row.original.name}`}>
                <PackageX /> <span className="hidden xl:inline">Descartar</span>
              </Button>
            )}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon" aria-label="Acciones">
                  <MoreHorizontal />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={() => setViewing(row.original)}>
                  <History /> Ver movimientos
                </DropdownMenuItem>
                {canAdjust && (
                  <DropdownMenuItem onClick={() => setWasting(row.original)}>
                    <PackageX /> Descartar (merma)
                  </DropdownMenuItem>
                )}
                {canEdit && (
                  <>
                    <DropdownMenuItem onClick={() => setAdjusting(row.original)}>
                      <SlidersHorizontal /> Ajustar
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => setPacking(row.original)}>
                      <Boxes /> Envases
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem
                      onClick={() => {
                        setEditing(row.original)
                        setFormOpen(true)
                      }}
                    >
                      <Pencil /> Editar insumo
                    </DropdownMenuItem>
                    <DropdownMenuItem variant="destructive" onClick={() => setDeleting(row.original)}>
                      <Trash2 /> Desactivar
                    </DropdownMenuItem>
                  </>
                )}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        ),
      },
    ],
    [canEdit, canAdjust],
  )

  const s = summary.data
  return (
    <div>
      <FreeLocksBanner kinds={['stock_items']} className="mb-4" />
      <PageHeader
        title="Stock"
        description="Insumos, niveles y valorización del inventario."
        actions={
          <>
            <Button variant="outline" asChild>
              <Link to="sugerencias">
                <ShoppingCart /> Sugerencias de compra
              </Link>
            </Button>
            {canEdit && (
              <>
                <Button variant="outline" asChild>
                  <Link to="conteo">
                    <ClipboardList /> Conteo físico
                  </Link>
                </Button>
                <Button
                  onClick={() => {
                    setEditing(null)
                    setFormOpen(true)
                  }}
                >
                  <Plus /> Nuevo insumo
                </Button>
              </>
            )}
          </>
        }
      />

      <div className="mb-6 grid gap-4 sm:grid-cols-3">
        <StatCard
          label="Valor del inventario"
          value={fmtMoney(s?.total_value_cents, { short: true })}
          icon={Wallet}
          hint={s ? `${s.item_count} insumos activos` : undefined}
          loading={summary.isLoading}
        />
        <StatCard
          label="Bajo mínimo"
          value={s?.low_count ?? 0}
          icon={AlertTriangle}
          tone={s?.low_count ? 'warning' : 'default'}
          hint="Conviene reponer pronto"
          loading={summary.isLoading}
        />
        <StatCard
          label="Sin stock"
          value={s?.out_count ?? 0}
          icon={Boxes}
          tone={s?.out_count ? 'danger' : 'success'}
          hint={s?.out_count ? 'Reponer cuanto antes' : 'Todo con existencia'}
          loading={summary.isLoading}
        />
      </div>

      <DataTable
        columns={columns}
        data={filtered}
        loading={items.isLoading}
        searchPlaceholder="Buscar insumo…"
        onRowClick={(i) => setViewing(i)}
        emptyTitle="No hay insumos para mostrar"
        emptyDescription="Probá cambiar los filtros o cargá un insumo nuevo."
        toolbar={
          <div className="flex flex-wrap items-center gap-2">
            <Select value={category} onValueChange={setCategory}>
              <SelectTrigger className="h-9 min-w-44" aria-label="Filtrar por categoría">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todas las categorías</SelectItem>
                {cats.data?.map((c) => (
                  <SelectItem key={c.id} value={String(c.id)}>
                    {c.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Tabs value={status} onValueChange={(v) => setStatus(v as StatusFilter)}>
              <TabsList>
                <TabsTrigger value="all">Todos</TabsTrigger>
                <TabsTrigger value="ok">OK</TabsTrigger>
                <TabsTrigger value="low">Bajos</TabsTrigger>
                <TabsTrigger value="out">Sin stock</TabsTrigger>
              </TabsList>
            </Tabs>
          </div>
        }
      />

      <AdjustDialog item={adjusting} onOpenChange={(o) => !o && setAdjusting(null)} />
      <DiscardDialog item={wasting} onOpenChange={(o) => !o && setWasting(null)} />
      <PackagesDialog item={packing} onOpenChange={(o) => !o && setPacking(null)} />
      <MovementsSheet item={viewing} onOpenChange={(o) => !o && setViewing(null)} />
      <StockItemDialog open={formOpen} item={editing} onOpenChange={setFormOpen} />
      <ConfirmDialog
        open={!!deleting}
        onOpenChange={(o) => !o && setDeleting(null)}
        title="¿Desactivar insumo?"
        description={`${deleting?.name} dejará de aparecer en el stock y en los buscadores. El historial se conserva.`}
        confirmLabel="Desactivar"
        destructive
        onConfirm={() => deleting && deactivate.mutate(deleting.id, { onSuccess: () => setDeleting(null) })}
      />
    </div>
  )
}
