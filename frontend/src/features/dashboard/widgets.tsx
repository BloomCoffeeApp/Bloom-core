import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Coffee,
  Info,
  Lock,
  LockOpen,
  Receipt,
  Wrench,
} from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, XAxis, YAxis } from 'recharts'

import { EmptyState } from '@/components/empty-state'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { ChartContainer, ChartTooltip, type ChartConfig } from '@/components/ui/chart'
import { Skeleton } from '@/components/ui/skeleton'
import { BarList, chartColor, fmtMoneyCompact, MoneyTooltip } from '@/components/report-kit'
import { fmtDate, fmtMoney, fmtNumber, fmtPct, fmtRelative, fmtTime } from '@/lib/format'
import { cn } from '@/lib/utils'

import type { BaristaToday, CashCurrent, DayPoint, HourPoint, MixRow, OpenAlert, RecentSale, TopProduct } from './types'

export function Panel({
  title,
  description,
  action,
  children,
  className,
  contentClassName,
}: {
  title: string
  description?: ReactNode
  action?: ReactNode
  children: ReactNode
  className?: string
  contentClassName?: string
}) {
  return (
    <Card className={cn('rounded-2xl', className)}>
      <CardHeader>
        <CardTitle className="font-heading text-lg">{title}</CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
        {action && <CardAction>{action}</CardAction>}
      </CardHeader>
      <CardContent className={contentClassName}>{children}</CardContent>
    </Card>
  )
}

const hourlyConfig = {
  sales_cents: { label: 'Ventas', color: 'var(--chart-1)' },
  avg_cents: { label: 'Promedio', color: 'var(--chart-3)' },
} satisfies ChartConfig

export function HourlyChart({ data, mode, loading }: { data?: HourPoint[]; mode?: 'day' | 'avg'; loading?: boolean }) {
  if (loading && !data) return <Skeleton className="h-64 w-full rounded-xl" />
  if (!data?.length) return <EmptyState icon={Receipt} title="Todavía no hay ventas" description="Cuando registres ventas vas a ver la curva por hora." />
  const labels = {
    sales_cents: mode === 'avg' ? 'Promedio diario del período' : 'Ventas',
    avg_cents: mode === 'avg' ? 'Promedio 4 semanas previas' : 'Promedio mismo día (4 sem.)',
  }
  return (
    <ChartContainer config={hourlyConfig} className="aspect-auto h-64 w-full">
      <AreaChart data={data} margin={{ left: 4, right: 8, top: 8 }}>
        <defs>
          <linearGradient id="fillSales" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="var(--color-sales_cents)" stopOpacity={0.45} />
            <stop offset="95%" stopColor="var(--color-sales_cents)" stopOpacity={0.03} />
          </linearGradient>
        </defs>
        <CartesianGrid vertical={false} />
        <XAxis dataKey="label" tickLine={false} axisLine={false} tickMargin={8} minTickGap={16} />
        <YAxis tickLine={false} axisLine={false} width={64} tickFormatter={fmtMoneyCompact} />
        <ChartTooltip content={<MoneyTooltip labels={labels} />} />
        <Area
          dataKey="avg_cents"
          type="monotone"
          stroke="var(--color-avg_cents)"
          strokeDasharray="5 4"
          strokeWidth={2}
          fill="none"
          name={labels.avg_cents}
        />
        <Area
          dataKey="sales_cents"
          type="monotone"
          stroke="var(--color-sales_cents)"
          strokeWidth={2.5}
          fill="url(#fillSales)"
          name={labels.sales_cents}
        />
      </AreaChart>
    </ChartContainer>
  )
}

const dailyConfig = { sales_cents: { label: 'Ventas', color: 'var(--chart-2)' } } satisfies ChartConfig

export function DailyChart({ data, loading }: { data?: DayPoint[]; loading?: boolean }) {
  if (loading && !data) return <Skeleton className="h-56 w-full rounded-xl" />
  if (!data?.some((d) => d.sales_cents)) return <EmptyState title="Sin ventas en los últimos 30 días" />
  return (
    <ChartContainer config={dailyConfig} className="aspect-auto h-56 w-full">
      <BarChart data={data} margin={{ left: 4, right: 8, top: 8 }}>
        <CartesianGrid vertical={false} />
        <XAxis dataKey="label" tickLine={false} axisLine={false} tickMargin={8} minTickGap={12} />
        <YAxis tickLine={false} axisLine={false} width={64} tickFormatter={fmtMoneyCompact} />
        <ChartTooltip cursor={false} content={<MoneyTooltip labels={{ sales_cents: 'Ventas' }} />} />
        <Bar dataKey="sales_cents" fill="var(--color-sales_cents)" radius={[6, 6, 2, 2]} maxBarSize={28} />
      </BarChart>
    </ChartContainer>
  )
}

export function TopProducts({ data, loading }: { data?: TopProduct[]; loading?: boolean }) {
  if (loading && !data) return <ListSkeleton rows={6} />
  if (!data?.length) return <EmptyState title="Sin productos vendidos" />
  return (
    <BarList
      items={data.map((p) => ({
        key: String(p.product_id ?? p.name),
        label: p.name,
        value: p.sales_cents,
        hint: `× ${fmtNumber(p.qty, 0)}`,
      }))}
    />
  )
}

export function Donut({ data, loading, empty }: { data?: MixRow[]; loading?: boolean; empty: string }) {
  if (loading && !data) return <Skeleton className="mx-auto size-44 rounded-full" />
  if (!data?.length) return <EmptyState title={empty} />
  const config: ChartConfig = Object.fromEntries(data.map((d, i) => [d.key, { label: d.label, color: chartColor(i) }]))
  const total = data.reduce((s, d) => s + d.sales_cents, 0)
  return (
    <div className="flex flex-col items-center gap-4 sm:flex-row lg:flex-col xl:flex-row">
      <div className="relative">
        <ChartContainer config={config} className="aspect-square h-40">
          <PieChart>
            <ChartTooltip content={<MoneyTooltip />} />
            <Pie data={data} dataKey="sales_cents" nameKey="label" innerRadius={48} outerRadius={72} paddingAngle={2} strokeWidth={0}>
              {data.map((d, i) => (
                <Cell key={d.key} fill={chartColor(i)} />
              ))}
            </Pie>
          </PieChart>
        </ChartContainer>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-[10px] tracking-wide text-muted-foreground uppercase">Total</span>
          <span className="tabular text-sm font-semibold">{fmtMoney(total, { short: true })}</span>
        </div>
      </div>
      <ul className="w-full min-w-0 flex-1 space-y-1.5 text-sm">
        {data.slice(0, 6).map((d, i) => (
          <li key={d.key} className="flex items-center justify-between gap-2">
            <span className="flex min-w-0 items-center gap-2">
              <span className="size-2.5 shrink-0 rounded-[3px]" style={{ background: chartColor(i) }} />
              <span className="truncate">{d.label}</span>
            </span>
            <span className="tabular shrink-0 text-muted-foreground">{fmtPct(d.pct, 0)}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

const SEVERITY: Record<string, { icon: typeof Info; cls: string }> = {
  critical: { icon: AlertTriangle, cls: 'bg-destructive/10 text-destructive' },
  warning: { icon: AlertTriangle, cls: 'bg-warning/20 text-warning-foreground dark:text-warning' },
  info: { icon: Info, cls: 'bg-info/15 text-info' },
}

export function AlertsPanel({ data, loading, failed }: { data?: OpenAlert[]; loading?: boolean; failed?: boolean }) {
  const order = { critical: 0, warning: 1, info: 2 } as Record<string, number>
  const items = [...(data ?? [])].sort((a, b) => (order[a.severity ?? 'info'] ?? 3) - (order[b.severity ?? 'info'] ?? 3)).slice(0, 5)
  return (
    <Panel
      title="Alertas"
      description={data?.length ? `${data.length} abiertas` : undefined}
      action={
        <Button variant="ghost" size="sm" asChild>
          <Link to="/avisos">
            Ver todas <ArrowRight />
          </Link>
        </Button>
      }
    >
      {loading ? (
        <ListSkeleton rows={4} />
      ) : failed || !items.length ? (
        <div className="flex flex-col items-center gap-2 py-6 text-center text-sm text-muted-foreground">
          <CheckCircle2 className="size-8 text-success" />
          {failed ? 'No hay alertas para mostrar' : 'Todo en orden, no hay alertas abiertas'}
        </div>
      ) : (
        <ul className="space-y-2">
          {items.map((a) => {
            const s = SEVERITY[a.severity ?? 'info'] ?? SEVERITY.info
            const Icon = s.icon
            const body = (
              <div className="flex items-start gap-3 rounded-xl p-2 transition-colors hover:bg-muted/60">
                <div className={cn('flex size-8 shrink-0 items-center justify-center rounded-lg', s.cls)}>
                  <Icon className="size-4" />
                </div>
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{a.title}</p>
                  {a.message && <p className="line-clamp-2 text-xs text-muted-foreground">{a.message}</p>}
                </div>
                {a.created_at && <span className="ml-auto shrink-0 text-[11px] text-muted-foreground">{fmtRelative(a.created_at)}</span>}
              </div>
            )
            return <li key={a.id}>{a.link && a.link.startsWith('/') ? <Link to={a.link}>{body}</Link> : body}</li>
          })}
        </ul>
      )}
    </Panel>
  )
}

function fmtSeconds(s?: number | null) {
  return s == null ? '—' : `${fmtNumber(s, 0)} s`
}

export function RecipeCard({ data, loading, failed }: { data?: BaristaToday; loading?: boolean; failed?: boolean }) {
  const esp = data?.current_espresso
  const r = esp?.recipe
  return (
    <Panel
      title="Receta del día"
      description={esp?.coffee?.name ?? 'Espresso en uso'}
      action={
        <Button variant="ghost" size="sm" asChild>
          <Link to="/barista">
            Barista <ArrowRight />
          </Link>
        </Button>
      }
    >
      {loading ? (
        <ListSkeleton rows={3} />
      ) : failed || !r ? (
        <div className="flex flex-col items-center gap-2 py-6 text-center text-sm text-muted-foreground">
          <Coffee className="size-8" />
          No hay una receta de espresso marcada como actual
        </div>
      ) : (
        <div className="space-y-4">
          <div className="flex items-center gap-3 rounded-xl bg-primary/10 p-3">
            <div className="flex size-10 items-center justify-center rounded-xl bg-primary text-primary-foreground">
              <Coffee className="size-5" />
            </div>
            <div className="min-w-0">
              <p className="truncate font-medium">{r.name}</p>
              {esp?.coffee?.days_off_roast != null && (
                <p className="text-xs text-muted-foreground">
                  {esp.coffee.days_off_roast} días de tostado
                  {esp.coffee.window ? ` · ${esp.coffee.window}` : ''}
                </p>
              )}
            </div>
          </div>
          <dl className="grid grid-cols-3 gap-2 text-center">
            {[
              ['Dosis', r.dose_g != null ? `${fmtNumber(r.dose_g, 1)} g` : '—'],
              ['Rinde', r.yield_g != null ? `${fmtNumber(r.yield_g, 1)} g` : '—'],
              ['Tiempo', r.time_min_s != null ? `${r.time_min_s}–${r.time_max_s ?? ''} s` : '—'],
              ['Temp.', r.temp_c != null ? `${fmtNumber(r.temp_c, 1)} °C` : '—'],
              ['Molienda', r.grind_ref ?? '—'],
              ['Shots hoy', String(data?.shots_today ?? 0)],
            ].map(([k, v]) => (
              <div key={k} className="rounded-lg border p-2">
                <dt className="text-[11px] text-muted-foreground">{k}</dt>
                <dd className="tabular truncate text-sm font-semibold">{v}</dd>
              </div>
            ))}
          </dl>
          {data?.avg_time_today != null && (
            <p className="text-xs text-muted-foreground">Tiempo promedio hoy: {fmtSeconds(data.avg_time_today)}</p>
          )}
          {!!data?.maintenance_due?.length && (
            <div className="space-y-1 rounded-xl bg-warning/15 p-2.5 text-xs">
              {data.maintenance_due.slice(0, 3).map((m) => (
                <p key={m.id} className="flex items-center gap-1.5">
                  <Wrench className="size-3.5" /> {m.name}
                  {m.equipment_name ? ` · ${m.equipment_name}` : ''}
                </p>
              ))}
            </div>
          )}
        </div>
      )}
    </Panel>
  )
}

function num(v: unknown): number | undefined {
  return typeof v === 'number' && Number.isFinite(v) ? v : undefined
}

export function CashCard({ data, loading, failed, canOperate }: { data?: CashCurrent | null; loading?: boolean; failed?: boolean; canOperate: boolean }) {
  const open = !!data && !failed
  const sales = num(data?.sales_cents) ?? num(data?.total_sales_cents)
  return (
    <Panel title="Caja" description={open ? 'Abierta' : 'Cerrada'}>
      {loading ? (
        <ListSkeleton rows={2} />
      ) : (
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <div
              className={cn(
                'flex size-11 items-center justify-center rounded-xl',
                open ? 'bg-success/15 text-success' : 'bg-muted text-muted-foreground',
              )}
            >
              {open ? <LockOpen className="size-5" /> : <Lock className="size-5" />}
            </div>
            <div className="min-w-0 text-sm">
              {open ? (
                <>
                  <p className="font-medium">
                    Abierta {typeof data?.opened_at === 'string' ? `a las ${fmtTime(data.opened_at)}` : ''}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {typeof data?.opened_at === 'string' && fmtDate(data.opened_at)}
                    {typeof data?.opened_by_name === 'string' ? ` · ${data.opened_by_name}` : ''}
                  </p>
                </>
              ) : (
                <p className="text-muted-foreground">No hay una caja abierta</p>
              )}
            </div>
          </div>
          {open && (
            <div className="grid grid-cols-2 gap-2">
              <div className="rounded-lg border p-2">
                <p className="text-[11px] text-muted-foreground">Fondo inicial</p>
                <p className="tabular text-sm font-semibold">{fmtMoney(num(data?.opening_cents) ?? null)}</p>
              </div>
              <div className="rounded-lg border p-2">
                <p className="text-[11px] text-muted-foreground">Ventas</p>
                <p className="tabular text-sm font-semibold">{fmtMoney(sales ?? null)}</p>
              </div>
            </div>
          )}
          {canOperate && (
            <Button asChild className="h-10 w-full" variant={open ? 'outline' : 'default'}>
              <Link to="/caja">{open ? 'Ir a caja' : 'Abrir caja'}</Link>
            </Button>
          )}
        </div>
      )}
    </Panel>
  )
}

const CHANNEL: Record<string, string> = { salon: 'Salón', llevar: 'Para llevar', delivery: 'Delivery' }

export function RecentSales({ data, loading }: { data?: RecentSale[]; loading?: boolean }) {
  if (loading && !data) return <ListSkeleton rows={6} />
  if (!data?.length) return <EmptyState icon={Receipt} title="Todavía no hay tickets" />
  return (
    <ul className="divide-y">
      {data.map((s) => (
        <li key={s.id} className="flex items-center gap-3 py-2.5 first:pt-0 last:pb-0">
          <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-muted text-xs font-semibold tabular">
            #{s.number}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm">
              {fmtNumber(s.items_count, 0)} {s.items_count === 1 ? 'ítem' : 'ítems'} · {CHANNEL[s.channel] ?? s.channel}
              {s.payment_methods.length > 0 && (
                <span className="text-muted-foreground"> · {s.payment_methods.join(' + ')}</span>
              )}
            </p>
            <p className="text-xs text-muted-foreground">
              {fmtRelative(s.ts)}
              {s.user_name ? ` · ${s.user_name}` : ''}
            </p>
          </div>
          <div className="text-right">
            <p className={cn('tabular text-sm font-semibold', s.status === 'voided' && 'text-muted-foreground line-through')}>
              {fmtMoney(s.total_cents)}
            </p>
            {s.status === 'voided' && (
              <Badge variant="destructive" className="h-4 px-1.5 text-[10px]">
                Anulado
              </Badge>
            )}
          </div>
        </li>
      ))}
    </ul>
  )
}

export function ListSkeleton({ rows }: { rows: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-8 w-full" />
      ))}
    </div>
  )
}

