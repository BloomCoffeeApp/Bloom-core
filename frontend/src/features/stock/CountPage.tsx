import { ArrowLeft, CheckCheck, ClipboardCheck, ClipboardList, Plus, X } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'

import { ConfirmDialog } from '@/components/confirm-dialog'
import { EmptyState } from '@/components/empty-state'
import { PageHeader } from '@/components/page-header'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Progress } from '@/components/ui/progress'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { useDepsChanged } from '@/hooks/use-deps-changed'
import { fmtDateTime, fmtMoney, fmtNumber, fmtQty } from '@/lib/format'
import { cn } from '@/lib/utils'

import { useCount, useCountAction, useCounts, useCreateCount, useSetCounted, useStockCategories } from './api'
import type { CountItem, InventoryCount } from './types'

const COUNT_STATUS: Record<InventoryCount['status'], { label: string; cls: string }> = {
  open: { label: 'Abierto', cls: 'bg-info/15 text-info' },
  applied: { label: 'Aplicado', cls: 'bg-success/15 text-success' },
  cancelled: { label: 'Cancelado', cls: 'bg-muted text-muted-foreground' },
}

function NewCountDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const cats = useStockCategories()
  const create = useCreateCount()
  const navigate = useNavigate()
  const [category, setCategory] = useState('all')
  const [notes, setNotes] = useState('')
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Nuevo conteo físico</DialogTitle>
          <DialogDescription>Tomamos una foto del stock actual para compararla con lo que cuentes.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-4">
          <div className="grid gap-1.5">
            <Label>¿Qué vas a contar?</Label>
            <Select value={category} onValueChange={setCategory}>
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos los insumos</SelectItem>
                {cats.data?.map((c) => (
                  <SelectItem key={c.id} value={String(c.id)}>
                    {c.name} ({c.item_count})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="cnt-notes">Notas (opcional)</Label>
            <Input id="cnt-notes" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Ej.: inventario de fin de mes" />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button
            disabled={create.isPending}
            onClick={() =>
              create.mutate(
                { category_id: category === 'all' ? null : Number(category), notes: notes || undefined },
                {
                  onSuccess: (c) => {
                    onOpenChange(false)
                    navigate(`/stock/conteo/${c.id}`)
                  },
                },
              )
            }
          >
            Empezar conteo
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export function CountListPage() {
  const counts = useCounts()
  const [open, setOpen] = useState(false)
  return (
    <div>
      <PageHeader
        title="Conteo físico"
        description="Cargá lo que hay en el depósito y ajustamos el stock por diferencia."
        actions={
          <>
            <Button variant="outline" asChild>
              <Link to="/stock">
                <ArrowLeft /> Volver a stock
              </Link>
            </Button>
            <Button onClick={() => setOpen(true)}>
              <Plus /> Nuevo conteo
            </Button>
          </>
        }
      />
      {counts.isLoading ? (
        <div className="grid gap-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-20 rounded-2xl" />
          ))}
        </div>
      ) : !counts.data?.length ? (
        <EmptyState
          icon={ClipboardList}
          title="Todavía no hiciste conteos"
          description="Un conteo periódico ayuda a detectar faltantes y mermas no registradas."
          action={
            <Button onClick={() => setOpen(true)}>
              <Plus /> Empezar el primero
            </Button>
          }
        />
      ) : (
        <div className="grid gap-3">
          {counts.data.map((c) => (
            <Link key={c.id} to={`/stock/conteo/${c.id}`}>
              <Card className="rounded-2xl transition-colors hover:bg-muted/40">
                <CardContent className="flex flex-wrap items-center gap-4">
                  <div className="flex size-11 items-center justify-center rounded-xl bg-primary/10 text-primary">
                    <ClipboardCheck className="size-5" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="font-medium">
                      Conteo #{c.id} {c.notes ? <span className="text-muted-foreground">· {c.notes}</span> : null}
                    </p>
                    <p className="text-sm text-muted-foreground">
                      {fmtDateTime(c.created_at)} · {c.user_name ?? '—'} · {c.counted_items}/{c.total_items} contados
                    </p>
                  </div>
                  {c.status !== 'open' && c.counted_items > 0 && (
                    <span className={cn('tabular text-sm font-medium', c.diff_value_cents < 0 ? 'text-destructive' : 'text-success')}>
                      {c.diff_value_cents > 0 ? '+' : ''}
                      {fmtMoney(c.diff_value_cents)}
                    </span>
                  )}
                  <Badge variant="secondary" className={COUNT_STATUS[c.status].cls}>
                    {COUNT_STATUS[c.status].label}
                  </Badge>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
      <NewCountDialog open={open} onOpenChange={setOpen} />
    </div>
  )
}

function CountRow({ item, editable, onSave }: { item: CountItem; editable: boolean; onSave: (v: number | null) => void }) {
  const [text, setText] = useState(item.counted_qty == null ? '' : String(item.counted_qty))
  // Follow server-side changes to the counted quantity.
  if (useDepsChanged([item.counted_qty], false)) setText(item.counted_qty == null ? '' : String(item.counted_qty))
  const commit = () => {
    const t = text.trim().replace(',', '.')
    const v = t === '' ? null : Number(t)
    if (v != null && (!Number.isFinite(v) || v < 0)) return
    if (v !== item.counted_qty) onSave(v)
  }
  const diff = item.diff_qty
  return (
    <div
      className={cn(
        'grid grid-cols-[1fr_auto] items-center gap-3 rounded-xl border bg-card px-4 py-3 sm:grid-cols-[1fr_8rem_10rem_8rem]',
        diff != null && Math.abs(diff) > 1e-9 && (diff < 0 ? 'border-destructive/40 bg-destructive/5' : 'border-success/40 bg-success/5'),
      )}
    >
      <div className="min-w-0">
        <p className="truncate font-medium">{item.name}</p>
        <p className="text-xs text-muted-foreground sm:hidden">Sistema: {fmtQty(item.expected_qty, item.unit)}</p>
      </div>
      <div className="tabular hidden text-right text-sm text-muted-foreground sm:block">{fmtQty(item.expected_qty, item.unit)}</div>
      <div className="relative">
        <Input
          inputMode="decimal"
          disabled={!editable}
          className="tabular h-11 pr-9 text-right text-base"
          placeholder="—"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onBlur={commit}
          onKeyDown={(e) => {
            if (e.key === 'Enter') (e.target as HTMLInputElement).blur()
          }}
        />
        <span className="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 text-xs text-muted-foreground">{item.unit}</span>
      </div>
      <div className="col-span-2 text-right sm:col-span-1">
        {diff == null ? (
          <span className="text-xs text-muted-foreground">Sin contar</span>
        ) : Math.abs(diff) < 1e-9 ? (
          <span className="text-sm text-success">Coincide</span>
        ) : (
          <div className={cn('tabular text-sm font-semibold', diff < 0 ? 'text-destructive' : 'text-success')}>
            {diff > 0 ? '+' : ''}
            {fmtNumber(diff)} {item.unit}
            <div className="text-xs font-normal opacity-80">{fmtMoney(item.diff_value_cents)}</div>
          </div>
        )}
      </div>
    </div>
  )
}

export function CountDetailPage() {
  const id = Number(useParams().id)
  const { data, isLoading } = useCount(Number.isFinite(id) ? id : null)
  const setCounted = useSetCounted(id)
  const action = useCountAction(id)
  const [confirm, setConfirm] = useState<'apply' | 'cancel' | null>(null)

  const groups = useMemo(() => {
    const out = new Map<string, CountItem[]>()
    for (const it of data?.items ?? []) {
      const k = it.category_name ?? 'Sin categoría'
      out.set(k, [...(out.get(k) ?? []), it])
    }
    return [...out.entries()]
  }, [data])

  if (isLoading || !data) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-12 w-72" />
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-16 rounded-xl" />
        ))}
      </div>
    )
  }

  const editable = data.status === 'open'
  const pct = data.total_items ? (data.counted_items / data.total_items) * 100 : 0
  const withDiff = data.items.filter((i) => i.diff_qty != null && Math.abs(i.diff_qty) > 1e-9)

  return (
    <div>
      <PageHeader
        title={`Conteo #${data.id}`}
        description={`${fmtDateTime(data.created_at)} · ${data.user_name ?? ''}${data.notes ? ` · ${data.notes}` : ''}`}
        actions={
          <>
            <Button variant="outline" asChild>
              <Link to="/stock/conteo">
                <ArrowLeft /> Conteos
              </Link>
            </Button>
            <Badge variant="secondary" className={cn('h-8 px-3 text-sm', COUNT_STATUS[data.status].cls)}>
              {COUNT_STATUS[data.status].label}
            </Badge>
          </>
        }
      >
        <Card className="rounded-2xl">
          <CardContent className="flex flex-wrap items-center gap-6">
            <div className="min-w-48 flex-1 space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Progreso</span>
                <span className="tabular font-medium">
                  {data.counted_items} de {data.total_items}
                </span>
              </div>
              <Progress value={pct} className="h-2" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Con diferencia</p>
              <p className="tabular text-xl font-semibold">{withDiff.length}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Diferencia valorizada</p>
              <p className={cn('tabular text-xl font-semibold', data.diff_value_cents < 0 ? 'text-destructive' : data.diff_value_cents > 0 ? 'text-success' : '')}>
                {data.diff_value_cents > 0 ? '+' : ''}
                {fmtMoney(data.diff_value_cents)}
              </p>
            </div>
          </CardContent>
        </Card>
      </PageHeader>

      <div className="space-y-8">
        {groups.map(([cat, items]) => {
          const pending = items.filter((i) => i.counted_qty == null)
          return (
            <section key={cat} className="space-y-2">
              <div className="flex items-center justify-between gap-2">
                <h2 className="font-heading text-lg font-semibold">{cat}</h2>
                {editable && pending.length > 0 && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() =>
                      setCounted.mutate(pending.map((i) => ({ id: i.id, counted_qty: Math.max(i.expected_qty, 0) })))
                    }
                  >
                    <CheckCheck /> Sin diferencias en el resto
                  </Button>
                )}
              </div>
              <div className="hidden grid-cols-[1fr_8rem_10rem_8rem] gap-3 px-4 text-xs font-medium tracking-wide text-muted-foreground uppercase sm:grid">
                <span>Insumo</span>
                <span className="text-right">Sistema</span>
                <span className="text-right">Contado</span>
                <span className="text-right">Diferencia</span>
              </div>
              {items.map((it) => (
                <CountRow
                  key={it.id}
                  item={it}
                  editable={editable}
                  onSave={(v) => setCounted.mutate([{ id: it.id, counted_qty: v }])}
                />
              ))}
            </section>
          )
        })}
      </div>

      {editable && (
        <div className="sticky bottom-4 z-20 mt-8 rounded-2xl border bg-background/95 shadow-lg backdrop-blur supports-backdrop-filter:bg-background/80">
          <div className="flex flex-wrap items-center justify-end gap-2 px-4 py-3">
            <span className="mr-auto text-sm text-muted-foreground">
              Los ítems sin contar no se modifican.
            </span>
            <Button variant="outline" onClick={() => setConfirm('cancel')}>
              <X /> Cancelar conteo
            </Button>
            <Button size="lg" disabled={!data.counted_items || action.isPending} onClick={() => setConfirm('apply')}>
              <ClipboardCheck /> Aplicar conteo
            </Button>
          </div>
        </div>
      )}

      <ConfirmDialog
        open={confirm === 'apply'}
        onOpenChange={(o) => !o && setConfirm(null)}
        title="¿Aplicar el conteo?"
        description={`Se van a generar ${withDiff.length} ajustes de stock por diferencia (${fmtMoney(data.diff_value_cents)}). Esta acción no se puede deshacer.`}
        confirmLabel="Aplicar"
        onConfirm={() => action.mutate('apply')}
      />
      <ConfirmDialog
        open={confirm === 'cancel'}
        onOpenChange={(o) => !o && setConfirm(null)}
        title="¿Cancelar el conteo?"
        description="No se va a modificar el stock."
        confirmLabel="Cancelar conteo"
        destructive
        onConfirm={() => action.mutate('cancel')}
      />
    </div>
  )
}
