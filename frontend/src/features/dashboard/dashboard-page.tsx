import { format } from 'date-fns'
import { es } from 'date-fns/locale'
import { DollarSign, Percent, Receipt, ShoppingBag } from 'lucide-react'
import { useMemo, useState } from 'react'

import { StatCard } from '@/components/stat-card'
import { useHasFeature } from '@/features/license/api'
import { proModules } from '@pro'
import { presetRange, PresetToggle, type PresetKey } from '@/components/report-kit'
import { useAuth } from '@/lib/auth'
import { fmtDate, fmtMoney, fmtNumber, fmtPct } from '@/lib/format'

import { useBaristaToday, useCashCurrent, useDashboard, useOpenAlerts } from './api'
import {
  AlertsPanel,
  CashCard,
  DailyChart,
  Donut,
  HourlyChart,
  Panel,
  RecentSales,
  RecipeCard,
  TopProducts,
} from './widgets'

function greeting(d: Date) {
  const h = d.getHours()
  if (h < 6) return 'Buenas noches'
  if (h < 13) return 'Buen día'
  if (h < 20) return 'Buenas tardes'
  return 'Buenas noches'
}

const PRESETS: PresetKey[] = ['today', 'yesterday', '7d', '30d', 'month']

export function DashboardPage() {
  const { user, can } = useAuth()
  const [preset, setPreset] = useState<PresetKey>('today')
  const range = useMemo(() => presetRange(preset), [preset])
  const dash = useDashboard(range.from, range.to)
  const alerts = useOpenAlerts()
  // The Barista module must be in this build (Pro edition) and licensed.
  const baristaPro = useHasFeature('barista') && !!proModules.Barista
  const barista = useBaristaToday(can('barista', 'encargado') && !!baristaPro)
  const cash = useCashCurrent(can('cajero', 'encargado'))

  const d = dash.data
  const loading = dash.isLoading
  const showCosts = d?.show_costs ?? can('encargado')
  const now = new Date()
  const compareHint = d ? `vs ${d.compare_label}` : undefined
  const periodLabel =
    range.from === range.to ? fmtDate(range.from) : `${fmtDate(range.from)} al ${fmtDate(range.to)}`

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm text-muted-foreground first-letter:uppercase">
            {format(now, "EEEE d 'de' MMMM 'de' yyyy", { locale: es })}
          </p>
          <h1 className="font-heading text-3xl font-semibold tracking-tight">
            {greeting(now)}
            {user ? `, ${user.name.split(' ')[0]}` : ''}
          </h1>
        </div>
        <PresetToggle value={preset} onChange={setPreset} presets={PRESETS} />
      </div>

      {dash.isError && (
        <div className="rounded-2xl border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
          No se pudieron cargar los indicadores: {(dash.error as Error).message}
        </div>
      )}

      <div className={showCosts ? 'grid gap-4 sm:grid-cols-2 xl:grid-cols-4' : 'grid gap-4 sm:grid-cols-3'}>
        <StatCard
          label="Ventas"
          icon={DollarSign}
          loading={loading}
          value={fmtMoney(d?.kpis.sales_cents)}
          delta={d?.deltas.sales_cents}
          hint={compareHint}
        />
        <StatCard
          label="Tickets"
          icon={Receipt}
          loading={loading}
          value={fmtNumber(d?.kpis.tickets, 0)}
          delta={d?.deltas.tickets}
          hint={compareHint}
        />
        <StatCard
          label="Ticket promedio"
          icon={ShoppingBag}
          loading={loading}
          value={fmtMoney(d?.kpis.avg_ticket_cents)}
          delta={d?.deltas.avg_ticket_cents}
          hint={compareHint}
        />
        {showCosts && (
          <StatCard
            label="Margen bruto estimado"
            icon={Percent}
            tone="success"
            loading={loading}
            value={fmtMoney(d?.kpis.gross_margin_cents)}
            delta={d?.deltas.gross_margin_cents}
            hint={d?.kpis.margin_pct != null ? `${fmtPct(d.kpis.margin_pct)} de las ventas` : compareHint}
          />
        )}
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Panel
          className="lg:col-span-2"
          title="Ventas por hora"
          description={
            d?.hourly_mode === 'avg'
              ? 'Promedio diario del período vs las 4 semanas anteriores'
              : `${periodLabel} vs promedio del mismo día (últimas 4 semanas)`
          }
        >
          <HourlyChart data={d?.hourly} mode={d?.hourly_mode} loading={loading} />
        </Panel>
        <AlertsPanel data={alerts.data} loading={alerts.isLoading} failed={alerts.isError} />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Panel className="lg:col-span-2" title="Últimos 30 días" description="Ventas diarias">
          <DailyChart data={d?.daily} loading={loading} />
        </Panel>
        <div className="grid gap-4">
          {can('barista', 'encargado') && (
            <RecipeCard data={barista.data} loading={barista.isLoading} failed={barista.isError} />
          )}
          {can('cajero', 'encargado') && (
            <CashCard data={cash.data} loading={cash.isLoading} failed={cash.isError} canOperate={can('cajero', 'encargado')} />
          )}
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <Panel title="Top 10 productos" description={periodLabel}>
          <TopProducts data={d?.top_products} loading={loading} />
        </Panel>
        <Panel title="Medios de pago" description={periodLabel}>
          <Donut data={d?.payment_mix} loading={loading} empty="Sin pagos registrados" />
        </Panel>
        <Panel title="Categorías" description={periodLabel} className="md:col-span-2 xl:col-span-1">
          <Donut data={d?.category_mix} loading={loading} empty="Sin ventas por categoría" />
        </Panel>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Panel className="lg:col-span-2" title="Últimos tickets">
          <RecentSales data={d?.recent_sales} loading={loading} />
        </Panel>
        <Panel title="Canales" description={periodLabel}>
          <Donut data={d?.channel_mix} loading={loading} empty="Sin ventas" />
        </Panel>
      </div>
    </div>
  )
}
