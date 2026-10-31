import { Cake, CreditCard, Plus, Search, Star, UserCheck, Users } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router'

import { type ColumnDef, DataTable } from '@/components/data-table'
import { PageHeader } from '@/components/page-header'
import { StatCard } from '@/components/stat-card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useDepsChanged } from '@/hooks/use-deps-changed'
import { fmtMoney, fmtNumber, fmtRelative } from '@/lib/format'
import { cn } from '@/lib/utils'

import { useCustomers, useCustomerStats } from './api'
import { CustomerAvatar, CustomerFormDialog } from './components'
import type { CustomerListItem, Segment } from './types'

const SEGMENTS: { value: Segment; label: string; icon?: typeof Users }[] = [
  { value: 'todos', label: 'Todos' },
  { value: 'frecuentes', label: 'Frecuentes' },
  { value: 'inactivos', label: 'Inactivos' },
  { value: 'cumpleanos_mes', label: 'Cumpleaños del mes' },
  { value: 'deudores', label: 'Con deuda' },
]

const SEGMENT_HINT: Record<Segment, string> = {
  todos: '',
  frecuentes: '4 o más visitas en los últimos 30 días.',
  inactivos: 'Compraron alguna vez, pero no vienen hace más de 30 días.',
  cumpleanos_mes: 'Cumplen años este mes: ¡buen momento para un mimo!',
  deudores: 'Clientes con saldo pendiente en cuenta corriente.',
}

function useDebounced<T>(value: T, ms = 250) {
  const [v, setV] = useState(value)
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms)
    return () => clearTimeout(t)
  }, [value, ms])
  return v
}

function birthdayLabel(b: string | null) {
  if (!b) return null
  const [, m, d] = b.split('-')
  return `${d}/${m}`
}

export function CustomersPage() {
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const segment = (params.get('segmento') as Segment) || 'todos'
  const [search, setSearch] = useState('')
  const q = useDebounced(search.trim())
  const { data, isLoading } = useCustomers(segment, q)
  const { data: stats, isLoading: statsLoading } = useCustomerStats()
  const [formOpen, setFormOpen] = useState(false)

  // `?nuevo=1` (e.g. from the command palette) opens the form once and is then dropped from the URL.
  const wantsNew = params.get('nuevo') === '1'
  if (useDepsChanged([wantsNew]) && wantsNew) setFormOpen(true)
  useEffect(() => {
    if (!wantsNew) return
    const next = new URLSearchParams(params)
    next.delete('nuevo')
    setParams(next, { replace: true })
  }, [wantsNew, params, setParams])

  const setSegment = (s: string) => {
    const next = new URLSearchParams(params)
    if (s === 'todos') next.delete('segmento')
    else next.set('segmento', s)
    setParams(next, { replace: true })
  }

  const columns = useMemo<ColumnDef<CustomerListItem, unknown>[]>(
    () => [
      {
        accessorKey: 'name',
        header: 'Cliente',
        cell: ({ row }) => {
          const c = row.original
          return (
            <div className="flex min-w-0 items-center gap-3">
              <CustomerAvatar id={c.id} name={c.name} />
              <div className="min-w-0">
                <p className="truncate font-medium">{c.name}</p>
                <p className="truncate text-xs text-muted-foreground">
                  {c.notes || c.email || (c.visits ? `${c.visits} visitas` : 'Sin compras todavía')}
                </p>
              </div>
            </div>
          )
        },
      },
      {
        accessorKey: 'phone',
        header: 'Teléfono',
        cell: ({ row }) => <span className="tabular text-muted-foreground">{row.original.phone ?? '—'}</span>,
      },
      {
        accessorKey: 'birthday',
        header: 'Cumple',
        cell: ({ row }) =>
          row.original.birthday ? (
            <span className="inline-flex items-center gap-1 text-muted-foreground">
              <Cake className="size-3.5" />
              {birthdayLabel(row.original.birthday)}
            </span>
          ) : (
            <span className="text-muted-foreground">—</span>
          ),
      },
      {
        accessorKey: 'points',
        header: 'Puntos',
        cell: ({ row }) => (
          <span className="tabular inline-flex items-center gap-1">
            <Star className="size-3.5 text-primary" />
            {fmtNumber(row.original.points, 0)}
          </span>
        ),
      },
      {
        accessorKey: 'balance_cents',
        header: 'Saldo',
        cell: ({ row }) => {
          const c = row.original
          if (c.balance_cents <= 0) return <span className="text-muted-foreground">—</span>
          const over = c.balance_cents > c.credit_limit_cents
          return (
            <Badge variant={over ? 'destructive' : 'secondary'} className="tabular">
              {fmtMoney(c.balance_cents)}
            </Badge>
          )
        },
      },
      {
        id: 'last_visit',
        accessorFn: (c) => (c.last_visit_at ? new Date(c.last_visit_at).getTime() : 0),
        header: 'Última visita',
        cell: ({ row }) => {
          const c = row.original
          if (!c.last_visit_at) return <span className="text-muted-foreground">Nunca</span>
          return (
            <div className="flex items-center gap-2">
              <span className="first-letter:uppercase">{fmtRelative(c.last_visit_at)}</span>
              {c.visits_30d >= 4 && (
                <Badge variant="outline" className="border-success/40 text-success">
                  Frecuente
                </Badge>
              )}
            </div>
          )
        },
      },
    ],
    [],
  )

  return (
    <div>
      <PageHeader
        title="Clientes"
        description="Conocé a tus clientes: preferencias, consumos, puntos y cuenta corriente."
        actions={
          <Button onClick={() => setFormOpen(true)}>
            <Plus /> Nuevo cliente
          </Button>
        }
      />

      <div className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Clientes"
          value={fmtNumber(stats?.total, 0)}
          icon={Users}
          loading={statsLoading}
          hint={stats ? `${stats.nuevos_mes} nuevos este mes` : undefined}
        />
        <StatCard
          label="Activos (30 días)"
          value={fmtNumber(stats?.activos_30d, 0)}
          icon={UserCheck}
          tone="success"
          loading={statsLoading}
          hint={stats?.total ? `${Math.round((stats.activos_30d / stats.total) * 100)}% del total` : undefined}
        />
        <StatCard
          label="Deuda en cuenta corriente"
          value={fmtMoney(stats?.deuda_total_cents, { short: true })}
          icon={CreditCard}
          tone={stats?.deuda_total_cents ? 'warning' : 'default'}
          loading={statsLoading}
          hint={stats ? `${stats.deudores} ${stats.deudores === 1 ? 'cliente' : 'clientes'}` : undefined}
        />
        <StatCard
          label="Cumpleaños hoy"
          value={fmtNumber(stats?.cumpleanos_hoy.length, 0)}
          icon={Cake}
          tone={stats?.cumpleanos_hoy.length ? 'danger' : 'default'}
          loading={statsLoading}
          hint={
            stats?.cumpleanos_hoy.length ? (
              <span className="truncate">{stats.cumpleanos_hoy.map((c) => c.name).join(', ')}</span>
            ) : (
              'Nadie cumple hoy'
            )
          }
        />
      </div>

      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <Tabs value={segment} onValueChange={setSegment}>
          <TabsList className="h-auto flex-wrap">
            {SEGMENTS.map((s) => (
              <TabsTrigger key={s.value} value={s.value} className="px-3">
                {s.label}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
        <div className="relative w-full max-w-xs">
          <Search className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar por nombre, teléfono o email…"
            className="pl-9"
          />
        </div>
      </div>
      {SEGMENT_HINT[segment] && (
        <p className={cn('mb-3 text-sm text-muted-foreground')}>{SEGMENT_HINT[segment]}</p>
      )}

      <DataTable
        columns={columns}
        data={data}
        loading={isLoading}
        searchable={false}
        onRowClick={(c) => navigate(`/clientes/${c.id}`)}
        emptyTitle={q ? 'No encontramos clientes' : 'Todavía no hay clientes en este segmento'}
        emptyDescription={q ? 'Probá con otro nombre o teléfono.' : 'Creá uno nuevo o cargalos desde el POS al cobrar.'}
      />

      <CustomerFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        onSaved={(c) => navigate(`/clientes/${c.id}`)}
      />
    </div>
  )
}
