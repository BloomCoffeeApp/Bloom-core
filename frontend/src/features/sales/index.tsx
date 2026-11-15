import { subDays } from 'date-fns'
import { ChevronLeft, ChevronRight, Receipt, Search, ShoppingCart } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link, Route, Routes } from 'react-router'

import { DatePicker } from '@/components/date-picker'
import { EmptyState } from '@/components/empty-state'
import { PageHeader } from '@/components/page-header'
import { StatCard } from '@/components/stat-card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { fmtDate, fmtDateTime, fmtMoney, fmtNumber, isoDate, PAYMENT_LABEL } from '@/lib/format'
import { cn } from '@/lib/utils'

import { usePaymentMethods, useSales } from './api'
import { CourtesyBadge } from './courtesy-badge'
import { SaleDetailSheet } from './detail-sheet'
import { CHANNEL_LABEL, type SalesFilters } from './types'

type Preset = 'today' | 'yesterday' | '7d' | '30d' | 'range'
const PRESETS: { id: Preset; label: string }[] = [
  { id: 'today', label: 'Hoy' },
  { id: 'yesterday', label: 'Ayer' },
  { id: '7d', label: '7 días' },
  { id: '30d', label: '30 días' },
  { id: 'range', label: 'Rango' },
]

function presetDates(p: Preset): { from: string; to: string } {
  const today = new Date()
  switch (p) {
    case 'yesterday':
      return { from: isoDate(subDays(today, 1)), to: isoDate(subDays(today, 1)) }
    case '7d':
      return { from: isoDate(subDays(today, 6)), to: isoDate(today) }
    case '30d':
      return { from: isoDate(subDays(today, 29)), to: isoDate(today) }
    default:
      return { from: isoDate(today), to: isoDate(today) }
  }
}

const PAGE_SIZE = 50

function SalesPage() {
  const [preset, setPreset] = useState<Preset>('today')
  const [range, setRange] = useState(presetDates('7d'))
  const [status, setStatus] = useState('all')
  const [method, setMethod] = useState('all')
  const [number, setNumber] = useState('')
  const [page, setPage] = useState(1)
  const [selected, setSelected] = useState<number | null>(null)
  const { data: methods } = usePaymentMethods()

  const filters: SalesFilters = useMemo(() => {
    const d = preset === 'range' ? range : presetDates(preset)
    const n = Number(number)
    return {
      ...(n > 0 ? {} : { date_from: d.from, date_to: d.to }),
      status: status === 'all' ? undefined : status,
      method: method === 'all' ? undefined : method,
      number: n > 0 ? n : undefined,
      page,
      page_size: PAGE_SIZE,
    }
  }, [preset, range, status, method, number, page])
  const { data, isLoading, isFetching } = useSales(filters)
  const pages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1
  const reset = <T,>(fn: (v: T) => void) => (v: T) => {
    fn(v)
    setPage(1)
  }

  return (
    <>
      <PageHeader
        title="Ventas"
        description="Historial de tickets, reimpresión y anulaciones"
        actions={
          <Button size="lg" asChild>
            <Link to="/pos">
              <ShoppingCart /> Nueva venta
            </Link>
          </Button>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="flex rounded-xl border bg-card p-1">
          {PRESETS.map((p) => (
            <button
              key={p.id}
              onClick={() => reset(setPreset)(p.id)}
              className={cn(
                'h-9 rounded-lg px-3 text-sm font-medium transition-colors',
                preset === p.id ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-muted',
              )}
            >
              {p.label}
            </button>
          ))}
        </div>
        {preset === 'range' && (
          <div className="flex items-center gap-2">
            <DatePicker aria-label="Desde" className="h-10 w-40" value={range.from} max={range.to} onChange={(v) => reset(setRange)({ ...range, from: v })} />
            <span className="text-muted-foreground">a</span>
            <DatePicker aria-label="Hasta" className="h-10 w-40" value={range.to} min={range.from} onChange={(v) => reset(setRange)({ ...range, to: v })} />
          </div>
        )}
        <Select value={status} onValueChange={reset(setStatus)}>
          <SelectTrigger className="h-10 w-40" aria-label="Filtrar por estado">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todos los estados</SelectItem>
            <SelectItem value="completed">Completadas</SelectItem>
            <SelectItem value="voided">Anuladas</SelectItem>
            <SelectItem value="courtesy">Cortesías</SelectItem>
          </SelectContent>
        </Select>
        <Select value={method} onValueChange={reset(setMethod)}>
          <SelectTrigger className="h-10 w-44" aria-label="Filtrar por medio de pago">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todos los medios</SelectItem>
            {methods?.map((m) => (
              <SelectItem key={m.code} value={m.code}>
                {m.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <div className="relative">
          <Search className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            inputMode="numeric"
            placeholder="N° de ticket"
            className="h-10 w-36 pl-9"
            value={number}
            onChange={(e) => reset(setNumber)(e.target.value.replace(/\D/g, ''))}
          />
        </div>
      </div>

      <div className="mb-4 grid gap-4 sm:grid-cols-3">
        <StatCard label="Tickets" value={fmtNumber(data?.total ?? 0, 0)} icon={Receipt} loading={isLoading} />
        <StatCard label="Total vendido" value={fmtMoney(data?.sum_total_cents ?? 0)} icon={ShoppingCart} tone="success" loading={isLoading} hint="Sin anuladas" />
        <StatCard
          label="Período"
          value={filters.number ? `Ticket #${filters.number}` : filters.date_from === filters.date_to ? fmtDate(`${filters.date_from}T12:00:00`) : `${fmtDate(`${filters.date_from}T12:00:00`)} – ${fmtDate(`${filters.date_to}T12:00:00`)}`}
          loading={false}
        />
      </div>

      <Card className="gap-0 overflow-hidden rounded-2xl py-0">
        {isLoading ? (
          <div className="space-y-2 p-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : !data?.items.length ? (
          <div className="p-6">
            <EmptyState icon={Receipt} title="No hay ventas" description="Probá con otro período o filtro." />
          </div>
        ) : (
          <Table className={cn(isFetching && 'opacity-70')}>
            <TableHeader>
              <TableRow>
                <TableHead className="w-20">N°</TableHead>
                <TableHead>Fecha</TableHead>
                <TableHead>Canal</TableHead>
                <TableHead>Cliente</TableHead>
                <TableHead>Medio</TableHead>
                <TableHead>Usuario</TableHead>
                <TableHead className="text-right">Ítems</TableHead>
                <TableHead className="text-right">Total</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.items.map((s) => (
                <TableRow key={s.id} className="h-12 cursor-pointer" onClick={() => setSelected(s.id)}>
                  <TableCell className="tabular font-medium">#{s.number}</TableCell>
                  <TableCell className="tabular text-muted-foreground">{fmtDateTime(s.ts)}</TableCell>
                  <TableCell>
                    {CHANNEL_LABEL[s.channel]}
                    {s.table_label && <span className="text-muted-foreground"> · M{s.table_label}</span>}
                  </TableCell>
                  <TableCell className="max-w-40 truncate">{s.customer_name ?? <span className="text-muted-foreground">—</span>}</TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-1">
                      {s.methods.map((m) => (
                        <Badge key={m} variant="secondary">
                          {methods?.find((x) => x.code === m)?.name ?? PAYMENT_LABEL[m] ?? m}
                        </Badge>
                      ))}
                    </div>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{s.user_name ?? '—'}</TableCell>
                  <TableCell className="tabular text-right">{fmtNumber(s.items_count)}</TableCell>
                  <TableCell className="text-right">
                    {s.status === 'voided' ? (
                      <span className="inline-flex items-center gap-2">
                        <Badge variant="destructive">Anulada</Badge>
                        <span className="tabular text-muted-foreground line-through">
                          {fmtMoney(s.is_courtesy ? s.courtesy_cents : s.total_cents)}
                        </span>
                      </span>
                    ) : s.is_courtesy ? (
                      <span className="inline-flex items-center gap-2" title={s.courtesy_reason ?? undefined}>
                        <CourtesyBadge />
                        <span className="tabular text-muted-foreground line-through">{fmtMoney(s.courtesy_cents)}</span>
                        <span className="tabular font-semibold">{fmtMoney(0)}</span>
                      </span>
                    ) : (
                      <span className="tabular font-semibold">{fmtMoney(s.total_cents)}</span>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>

      {data && data.total > PAGE_SIZE && (
        <div className="mt-3 flex items-center justify-end gap-2 text-sm text-muted-foreground">
          <span>
            Página {page} de {pages}
          </span>
          <Button variant="outline" size="icon-lg" disabled={page <= 1} onClick={() => setPage((p) => p - 1)} aria-label="Anterior">
            <ChevronLeft />
          </Button>
          <Button variant="outline" size="icon-lg" disabled={page >= pages} onClick={() => setPage((p) => p + 1)} aria-label="Siguiente">
            <ChevronRight />
          </Button>
        </div>
      )}

      <SaleDetailSheet id={selected} onOpenChange={(o) => !o && setSelected(null)} />
    </>
  )
}

export default function Module() {
  return (
    <Routes>
      <Route index element={<SalesPage />} />
      <Route path="*" element={<SalesPage />} />
    </Routes>
  )
}
