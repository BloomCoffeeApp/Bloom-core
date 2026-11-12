import {
  AlertTriangle,
  BarChart3,
  Camera,
  CheckCircle2,
  MoreHorizontal,
  Pencil,
  Plus,
  Receipt,
  Repeat,
  Tags,
  Trash2,
  Wallet,
} from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'

import { ConfirmDialog } from '@/components/confirm-dialog'
import { DataTable, type ColumnDef } from '@/components/data-table'
import { EmptyState } from '@/components/empty-state'
import { PageHeader } from '@/components/page-header'
import { StatCard } from '@/components/stat-card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useHasFeature } from '@/features/license/api'
import { fmtDate, fmtMoney, fmtPct } from '@/lib/format'
import { cn } from '@/lib/utils'

import { useDeleteExpense, useExpenses, useMonthResult, useRecurringExpenses, useSaveRecurring } from './api'
import { CategoriesDialog, ExpenseDialog, PayDialog, ReceiptDialog, RecurringDialog } from './dialogs'
import { MonthPicker } from './month-picker'
import { currentMonth, KIND_LABEL } from './utils'
import { useNow } from '@/hooks/use-now'
import type { Expense, RecurringExpense } from './types'

function StatusBadge({ e }: { e: Expense }) {
  if (e.status === 'paid')
    return (
      <Badge variant="outline" className="border-success/40 text-success">
        Pagado
      </Badge>
    )
  if (e.overdue) return <Badge variant="destructive">Vencido</Badge>
  return (
    <Badge variant="outline" className="border-warning/60 text-warning-foreground dark:text-warning">
      Pendiente
    </Badge>
  )
}

function ExpensesTab({ month }: { month: string }) {
  const [status, setStatus] = useState('all')
  const list = useExpenses(month, status === 'all' ? {} : { status })
  const [editing, setEditing] = useState<Expense | null>(null)
  const [creating, setCreating] = useState(false)
  const [paying, setPaying] = useState<Expense | null>(null)
  const [receipt, setReceipt] = useState<Expense | null>(null)
  const [deleting, setDeleting] = useState<Expense | null>(null)
  const del = useDeleteExpense()
  const reportsPro = useHasFeature('reports')
  const t = list.data?.totals
  const cats = list.data?.by_category ?? []

  const columns: ColumnDef<Expense, unknown>[] = [
    {
      accessorKey: 'date',
      header: 'Fecha',
      cell: ({ row }) => <span className="tabular whitespace-nowrap">{fmtDate(row.original.date)}</span>,
    },
    {
      accessorKey: 'description',
      header: 'Concepto',
      cell: ({ row }) => {
        const e = row.original
        return (
          <div className="min-w-0">
            <div className="flex items-center gap-1.5 font-medium">
              {e.description}
              {e.recurring_id && <Repeat className="size-3.5 text-muted-foreground" aria-label="Gasto fijo mensual" />}
              {e.has_receipt && <Camera className="size-3.5 text-muted-foreground" aria-label="Con comprobante" />}
            </div>
            <div className="text-xs text-muted-foreground">
              {e.category_name} · {KIND_LABEL[e.kind]}
              {e.notes ? ` · ${e.notes}` : ''}
            </div>
          </div>
        )
      },
    },
    {
      id: 'state',
      header: 'Estado',
      accessorFn: (e) => e.status,
      cell: ({ row }) => {
        const e = row.original
        return (
          <div className="space-y-0.5">
            <StatusBadge e={e} />
            <div className="text-xs text-muted-foreground">
              {e.status === 'pending'
                ? e.due_date && `Vence ${fmtDate(e.due_date)}`
                : [e.payment_method_name, e.from_cash ? 'de la caja' : null].filter(Boolean).join(' · ')}
            </div>
          </div>
        )
      },
    },
    {
      accessorKey: 'amount_cents',
      header: () => <div className="text-right">Monto</div>,
      cell: ({ row }) => <div className="tabular text-right font-medium">{fmtMoney(row.original.amount_cents)}</div>,
    },
    {
      id: 'actions',
      enableSorting: false,
      header: '',
      cell: ({ row }) => {
        const e = row.original
        return (
          <div className="flex justify-end gap-1" onClick={(ev) => ev.stopPropagation()}>
            {e.status === 'pending' && (
              <Button size="sm" variant="outline" onClick={() => setPaying(e)}>
                <CheckCircle2 /> Pagar
              </Button>
            )}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button size="icon" variant="ghost" aria-label={`Acciones de ${e.description}`}>
                  <MoreHorizontal />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onSelect={() => setEditing(e)}>
                  <Pencil /> Editar
                </DropdownMenuItem>
                <DropdownMenuItem onSelect={() => setReceipt(e)}>
                  <Camera /> Comprobante
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem variant="destructive" onSelect={() => setDeleting(e)}>
                  <Trash2 /> Borrar
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        )
      },
    },
  ]

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Gastos del mes"
          value={fmtMoney(t?.total_cents ?? 0, { short: true })}
          icon={Receipt}
          loading={list.isLoading}
          hint={t ? `${t.count} gastos` : undefined}
        />
        <StatCard label="Pagado" value={fmtMoney(t?.paid_cents ?? 0, { short: true })} icon={CheckCircle2} tone="success" loading={list.isLoading} />
        <StatCard
          label="Pendiente"
          value={fmtMoney(t?.pending_cents ?? 0, { short: true })}
          icon={AlertTriangle}
          tone={t?.overdue_cents ? 'danger' : 'warning'}
          loading={list.isLoading}
          hint={t?.overdue_cents ? `${fmtMoney(t.overdue_cents)} vencido` : undefined}
        />
        <StatCard
          label="Gastos fijos"
          value={fmtMoney(t?.fixed_cents ?? 0, { short: true })}
          icon={Wallet}
          loading={list.isLoading}
          hint={t ? `Variables ${fmtMoney(t.variable_cents, { short: true })}` : undefined}
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_20rem]">
        <DataTable
          columns={columns}
          data={list.data?.items}
          loading={list.isLoading}
          searchPlaceholder="Buscar gasto…"
          onRowClick={(e) => setEditing(e)}
          emptyTitle="Sin gastos este mes"
          emptyDescription="Cargá el alquiler, los servicios o lo que pagues para ver la ganancia real."
          toolbar={
            <div className="flex flex-wrap gap-2">
              <Select value={status} onValueChange={setStatus}>
                <SelectTrigger className="w-40" aria-label="Filtrar por estado">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Todos</SelectItem>
                  <SelectItem value="pending">Pendientes</SelectItem>
                  <SelectItem value="paid">Pagados</SelectItem>
                </SelectContent>
              </Select>
              <Button onClick={() => setCreating(true)}>
                <Plus /> Nuevo gasto
              </Button>
            </div>
          }
        />
        <Card className="h-fit">
          <CardHeader>
            <CardTitle className="text-base">Por categoría</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {cats.length === 0 && <p className="text-sm text-muted-foreground">Todavía no hay gastos este mes.</p>}
            {cats.map((c) => (
              <div key={c.category_id} className="space-y-1">
                <div className="flex justify-between gap-2 text-sm">
                  <span className="truncate">{c.name}</span>
                  <span className="tabular font-medium">{fmtMoney(c.total_cents)}</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-muted">
                  <div className="h-full rounded-full bg-primary" style={{ width: `${Math.max(c.pct, 2)}%` }} />
                </div>
                <div className="text-right text-xs text-muted-foreground">{fmtPct(c.pct)}</div>
              </div>
            ))}
            <Button asChild variant="outline" size="sm" className="w-full">
              <Link to="/reportes?tab=resultado">
                <BarChart3 /> {reportsPro ? 'Ver el resultado del mes' : 'Resultado del mes (Pro)'}
              </Link>
            </Button>
          </CardContent>
        </Card>
      </div>

      <ExpenseDialog open={creating || !!editing} expense={editing} onOpenChange={(o) => !o && (setCreating(false), setEditing(null))} />
      <PayDialog expense={paying} onOpenChange={(o) => !o && setPaying(null)} />
      <ReceiptDialog
        expense={receipt ? (list.data?.items.find((x) => x.id === receipt.id) ?? receipt) : null}
        onOpenChange={(o) => !o && setReceipt(null)}
      />
      <ConfirmDialog
        open={!!deleting}
        onOpenChange={(o) => !o && setDeleting(null)}
        title="¿Borrar este gasto?"
        description={
          deleting?.from_cash
            ? 'Salió de la caja: también se borra el egreso (solo si esa caja sigue abierta).'
            : deleting?.recurring_id
              ? 'Es un gasto fijo: este mes no se vuelve a generar.'
              : 'No se puede deshacer.'
        }
        confirmLabel="Borrar"
        destructive
        onConfirm={() => deleting && del.mutate(deleting.id, { onSuccess: () => setDeleting(null) })}
      />
    </div>
  )
}

function RecurringTab() {
  const list = useRecurringExpenses()
  const save = useSaveRecurring()
  const [editing, setEditing] = useState<RecurringExpense | null>(null)
  const [creating, setCreating] = useState(false)
  const rows = list.data ?? []
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-muted-foreground">
          Alquiler, sueldos, servicios, abonos: se generan solos cada mes como pendientes, con su vencimiento.
        </p>
        <Button onClick={() => setCreating(true)}>
          <Plus /> Nuevo gasto fijo
        </Button>
      </div>
      {rows.length === 0 && !list.isLoading ? (
        <EmptyState title="Sin gastos fijos" description="Cargá el alquiler o los sueldos una sola vez y se generan solos cada mes." />
      ) : (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {rows.map((r) => (
            <Card key={r.id} className={cn('gap-2 py-4', !r.active && 'opacity-60')}>
              <CardContent className="space-y-2 px-4">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="truncate font-medium">{r.description}</div>
                    <div className="text-xs text-muted-foreground">{r.category_name}</div>
                  </div>
                  <span className="tabular font-semibold">{fmtMoney(r.amount_cents)}</span>
                </div>
                <div className="text-xs text-muted-foreground">
                  Vence el día {r.day_of_month} de cada mes
                  {r.payment_method_name ? ` · ${r.payment_method_name}` : ''}
                </div>
                <div className="flex items-center justify-between gap-2 pt-1">
                  <label className="flex items-center gap-2 text-sm">
                    <Switch
                      checked={r.active}
                      onCheckedChange={(v) => save.mutate({ id: r.id, body: { active: v } })}
                      aria-label={`Generar ${r.description} cada mes`}
                    />
                    {r.active ? 'Activo' : 'Pausado'}
                  </label>
                  <Button size="sm" variant="ghost" onClick={() => setEditing(r)}>
                    <Pencil /> Editar
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
      <RecurringDialog open={creating || !!editing} item={editing} onOpenChange={(o) => !o && (setCreating(false), setEditing(null))} />
    </div>
  )
}

function ResultStrip({ month }: { month: string }) {
  const res = useMonthResult(month)
  const c = res.data?.current
  if (!c) return null
  const row = (label: string, cents: number, sign: '+' | '−' | '=') => (
    <div className="flex items-center justify-between gap-3 text-sm">
      <span className="text-muted-foreground">
        <span className="tabular mr-1.5 inline-block w-3 text-center">{sign}</span>
        {label}
      </span>
      <span className="tabular">{fmtMoney(cents)}</span>
    </div>
  )
  return (
    <Card data-testid="month-result">
      <CardContent className="grid gap-6 md:grid-cols-[minmax(0,1fr)_16rem] md:items-center">
        <div className="space-y-1.5">
          {row('Ventas', c.sales_cents, '+')}
          {row('Costo de mercadería', c.cogs_cents, '−')}
          {row('Cortesías y mermas', c.losses_cents, '−')}
          {row('Gastos', c.expenses_cents, '−')}
        </div>
        <div className="rounded-2xl bg-muted/60 p-4 text-center">
          <div className="text-sm text-muted-foreground">Ganancia real{res.data?.partial ? ' (hasta hoy)' : ''}</div>
          <div className={cn('tabular text-3xl font-semibold', c.profit_cents < 0 ? 'text-destructive' : 'text-success')}>
            {fmtMoney(c.profit_cents)}
          </div>
          {c.profit_pct != null && <div className="text-xs text-muted-foreground">{fmtPct(c.profit_pct)} de las ventas</div>}
          {!!c.expenses_upcoming_cents && (
            <div className="mt-1 text-xs text-muted-foreground">Faltan {fmtMoney(c.expenses_upcoming_cents)} de gastos de este mes</div>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

export default function ExpensesPage() {
  const now = useNow()
  const [month, setMonth] = useState(() => currentMonth())
  const [catsOpen, setCatsOpen] = useState(false)
  return (
    <div>
      <PageHeader
        title="Gastos"
        description="Lo que cuesta mantener el local abierto, para saber cuánto ganás de verdad."
        actions={
          <>
            <MonthPicker value={month} onChange={setMonth} max={currentMonth(now)} />
            <Button variant="outline" onClick={() => setCatsOpen(true)}>
              <Tags /> Categorías
            </Button>
          </>
        }
      />
      <div className="space-y-6">
        <ResultStrip month={month} />
        <Tabs defaultValue="month">
          <TabsList>
            <TabsTrigger value="month">Gastos del mes</TabsTrigger>
            <TabsTrigger value="recurring">Fijos mensuales</TabsTrigger>
          </TabsList>
          <TabsContent value="month" className="mt-4">
            <ExpensesTab month={month} />
          </TabsContent>
          <TabsContent value="recurring" className="mt-4">
            <RecurringTab />
          </TabsContent>
        </Tabs>
      </div>
      <CategoriesDialog open={catsOpen} onOpenChange={setCatsOpen} />
    </div>
  )
}
