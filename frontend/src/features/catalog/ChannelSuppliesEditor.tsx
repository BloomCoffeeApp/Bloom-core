import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2, Plus, Save, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'

import { useStockItems } from '../stock/api'
import { useSizes } from './api'

// Mirrors backend services/channel_supplies.py.
type SupplyChannel = 'salon' | 'llevar' | 'delivery'
interface SupplyRow {
  channel: SupplyChannel
  size_id: number | null
  stock_item_id: number
  qty: number
}
interface SuppliesOut {
  rows: (SupplyRow & { id: number; stock_item_name: string; unit: string | null })[]
  inherited: boolean
  category_rows: (SupplyRow & { stock_item_name: string })[]
  category_id: number | null
  category_name: string | null
}

const CHANNELS: { key: SupplyChannel; label: string; example: string }[] = [
  { key: 'salon', label: 'En el local', example: 'servilleta, sobre de azúcar' },
  { key: 'llevar', label: 'Para llevar', example: 'vaso, tapa, manga' },
  { key: 'delivery', label: 'Delivery', example: 'vaso, tapa, bolsa, precinto' },
]

const selectCls = 'h-11 min-w-0 rounded-md border border-input bg-background px-2 text-sm'

/**
 * «Insumos según el canal»: any stock item a sold unit consumes depending on how it's served.
 * Empty by default. A product without its own lists uses its category's; per-size rows replace the
 * base quantity for that size (0 = not used).
 */
export function ChannelSuppliesEditor({ owner, id }: { owner: 'product' | 'category'; id: number }) {
  const path = owner === 'product' ? `/products/${id}/channel-supplies` : `/product-categories/${id}/channel-supplies`
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['channel-supplies', owner, id], queryFn: () => api.get<SuppliesOut>(path) })
  const items = useStockItems()
  const sizes = useSizes()
  const [channel, setChannel] = useState<SupplyChannel>('llevar')
  const [rows, setRows] = useState<SupplyRow[]>([])
  const [dirty, setDirty] = useState(false)
  const [loaded, setLoaded] = useState<SuppliesOut | undefined>(undefined)
  if (q.data && q.data !== loaded) {
    // New data from the server (first load or after saving): adjust the form during render.
    setLoaded(q.data)
    setRows(q.data.rows.map(({ channel, size_id, stock_item_id, qty }) => ({ channel, size_id, stock_item_id, qty })))
    setDirty(false)
  }
  const save = useMutation({
    mutationFn: () => api.put<SuppliesOut>(path, { rows: rows.filter((r) => r.stock_item_id > 0) }),
    onSuccess: (out) => {
      qc.setQueryData(['channel-supplies', owner, id], out)
      toast.success('Insumos según el canal guardados')
    },
    onError: (e: Error) => toast.error(e.message),
  })
  const change = (next: SupplyRow[]) => {
    setRows(next)
    setDirty(true)
  }
  const mine = rows.map((r, i) => ({ r, i })).filter(({ r }) => r.channel === channel)
  const firstItem = items.data?.find((s) => s.active)?.id ?? 0

  if (q.isLoading) return <p className="text-sm text-muted-foreground">Cargando…</p>
  return (
    <div className="space-y-3" data-testid="channel-supplies">
      {owner === 'product' && q.data?.inherited && rows.length === 0 && (
        <p className="rounded-lg bg-muted px-3 py-2 text-xs">
          Usa los de la categoría «{q.data.category_name}» ({q.data.category_rows.length} insumos). Cargá los de este producto
          para reemplazarlos.
        </p>
      )}
      <div className="flex flex-wrap gap-1.5" role="tablist" aria-label="Canal">
        {CHANNELS.map((c) => {
          const n = rows.filter((r) => r.channel === c.key).length
          return (
            <Button
              key={c.key}
              type="button"
              role="tab"
              aria-selected={channel === c.key}
              variant={channel === c.key ? 'default' : 'outline'}
              className="h-11"
              onClick={() => setChannel(c.key)}
            >
              {c.label}
              {n > 0 && <span className="rounded-full bg-background/30 px-1.5 text-xs tabular-nums">{n}</span>}
            </Button>
          )
        })}
      </div>
      <p className="text-xs text-muted-foreground">
        Por unidad vendida {CHANNELS.find((c) => c.key === channel)!.label.toLowerCase()} (ej.: {CHANNELS.find((c) => c.key === channel)!.example}).
        Un tamaño puntual reemplaza la cantidad general (0 = no se usa).
      </p>
      {mine.length === 0 ? (
        <p className="text-sm text-muted-foreground">Sin insumos para este canal.</p>
      ) : (
        <ul className="space-y-2">
          {mine.map(({ r, i }) => (
            <li key={i} className="grid grid-cols-[1fr_auto] gap-2 sm:grid-cols-[2fr_1.3fr_5rem_auto]">
              <select
                className={cn(selectCls, 'col-span-2 sm:col-span-1')}
                value={r.stock_item_id}
                aria-label="Insumo"
                onChange={(e) => change(rows.map((x, j) => (j === i ? { ...x, stock_item_id: Number(e.target.value) } : x)))}
              >
                {(items.data ?? []).map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} ({s.unit})
                  </option>
                ))}
              </select>
              <select
                className={selectCls}
                value={r.size_id ?? ''}
                aria-label="Tamaño"
                onChange={(e) => change(rows.map((x, j) => (j === i ? { ...x, size_id: e.target.value ? Number(e.target.value) : null } : x)))}
              >
                <option value="">Todos los tamaños</option>
                {(sizes.data ?? []).map((s) => (
                  <option key={s.id} value={s.id}>
                    Solo {s.name}
                  </option>
                ))}
              </select>
              <Input
                type="number"
                inputMode="decimal"
                min={0}
                step="any"
                className="h-11 w-20"
                value={r.qty}
                aria-label="Cantidad por unidad"
                onChange={(e) => change(rows.map((x, j) => (j === i ? { ...x, qty: Math.max(0, Number(e.target.value) || 0) } : x)))}
              />
              <Button type="button" variant="ghost" className="size-11" aria-label="Quitar insumo" onClick={() => change(rows.filter((_, j) => j !== i))}>
                <Trash2 />
              </Button>
            </li>
          ))}
        </ul>
      )}
      {!items.isLoading && !firstItem && (
        <p className="rounded-lg bg-muted px-3 py-2 text-xs">
          Todavía no cargaste ningún insumo (vasos, tapas, servilletas…), por eso no se puede agregar. Creálos primero en{' '}
          <Link to="/stock" className="font-medium underline underline-offset-2">
            Stock
          </Link>
          .
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          variant="outline"
          className="h-11"
          disabled={!firstItem}
          onClick={() => change([...rows, { channel, size_id: null, stock_item_id: firstItem, qty: 1 }])}
        >
          <Plus /> Agregar insumo
        </Button>
        <Button type="button" className="h-11" disabled={!dirty || save.isPending} onClick={() => save.mutate()}>
          {save.isPending ? <Loader2 className="animate-spin" /> : <Save />} Guardar insumos
        </Button>
      </div>
    </div>
  )
}
