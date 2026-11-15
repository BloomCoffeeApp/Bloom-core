import {
  ArrowRight,
  Bell,
  Cake,
  CalendarX,
  Check,
  CheckCheck,
  CircleAlert,
  Clock,
  Coffee,
  CreditCard,
  Eye,
  FileWarning,
  Info,
  type LucideIcon,
  Package,
  PackageX,
  RefreshCw,
  ShieldCheck,
  TriangleAlert,
  UserX,
  Wallet,
  Wrench,
} from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router'

import { EmptyState } from '@/components/empty-state'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { fmtDateTime, fmtRelative } from '@/lib/format'
import { cn } from '@/lib/utils'

import { useAlerts, useReadAlert, useReadAll, useRefreshAlerts, useResolveAlert } from './api'
import type { Alert, AlertFilter, Severity } from './types'

const TYPE_ICON: Record<string, LucideIcon> = {
  stock_low: Package,
  stock_out: PackageX,
  lot_expiry: CalendarX,
  purchase_due: FileWarning,
  cash_stale: Wallet,
  birthday: Cake,
  roast_old: Coffee,
  maintenance: Wrench,
  debt_over_limit: CreditCard,
  staff_late: Clock,
  staff_absent: UserX,
}

const SEVERITY: Record<Severity, { label: string; icon: LucideIcon; chip: string; bar: string; heading: string }> = {
  critical: {
    label: 'Críticas',
    icon: CircleAlert,
    chip: 'bg-destructive/10 text-destructive',
    bar: 'bg-destructive',
    heading: 'text-destructive',
  },
  warning: {
    label: 'Advertencias',
    icon: TriangleAlert,
    chip: 'bg-warning/20 text-warning-foreground dark:text-warning',
    bar: 'bg-warning',
    heading: 'text-warning-foreground dark:text-warning',
  },
  info: {
    label: 'Para tener en cuenta',
    icon: Info,
    chip: 'bg-info/15 text-info',
    bar: 'bg-info',
    heading: 'text-info',
  },
}

const FILTERS: { value: AlertFilter; label: string }[] = [
  { value: 'active', label: 'Pendientes' },
  { value: 'open', label: 'Sin leer' },
  { value: 'read', label: 'Leídas' },
  { value: 'resolved', label: 'Resueltas' },
]

export function AlertsTab() {
  const [filter, setFilter] = useState<AlertFilter>('active')
  const { data, isLoading } = useAlerts(filter)
  const refresh = useRefreshAlerts()
  const readAll = useReadAll()
  const hasUnread = data?.some((a) => a.status === 'open')

  const groups = (['critical', 'warning', 'info'] as Severity[])
    .map((sev) => ({ sev, items: (data ?? []).filter((a) => a.severity === sev) }))
    .filter((g) => g.items.length)

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <ToggleGroup
          type="single"
          variant="outline"
          value={filter}
          onValueChange={(v) => v && setFilter(v as AlertFilter)}
        >
          {FILTERS.map((f) => (
            <ToggleGroupItem key={f.value} value={f.value} className="px-3">
              {f.label}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
        <div className="flex gap-2">
          {filter !== 'resolved' && (
            <Button variant="ghost" onClick={() => readAll.mutate(undefined)} disabled={!hasUnread || readAll.isPending}>
              <CheckCheck /> Marcar todas leídas
            </Button>
          )}
          <Button variant="outline" onClick={() => refresh.mutate()} disabled={refresh.isPending}>
            <RefreshCw className={cn(refresh.isPending && 'animate-spin')} /> Revisar ahora
          </Button>
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-20 w-full rounded-2xl" />
          ))}
        </div>
      ) : groups.length === 0 ? (
        filter === 'active' || filter === 'open' ? (
          <EmptyState
            icon={ShieldCheck}
            title="Todo en orden"
            description="No hay alertas pendientes. Revisamos stock, vencimientos, caja, equipos y clientes cada 5 minutos."
          />
        ) : (
          <EmptyState icon={Bell} title="No hay alertas acá" />
        )
      ) : (
        groups.map(({ sev, items }) => {
          const S = SEVERITY[sev]
          return (
            <section key={sev} className="space-y-2.5">
              <h3 className={cn('flex items-center gap-2 text-sm font-semibold', S.heading)}>
                <S.icon className="size-4" /> {S.label}
                <Badge variant="secondary" className="tabular">
                  {items.length}
                </Badge>
              </h3>
              <ul className="space-y-2">
                {items.map((a) => (
                  <AlertRow key={a.id} alert={a} />
                ))}
              </ul>
            </section>
          )
        })
      )}
    </div>
  )
}

function AlertRow({ alert: a }: { alert: Alert }) {
  const navigate = useNavigate()
  const read = useReadAlert()
  const resolve = useResolveAlert()
  const S = SEVERITY[a.severity] ?? SEVERITY.info
  const Icon = TYPE_ICON[a.type] ?? S.icon
  const unread = a.status === 'open'
  const resolved = a.status === 'resolved'

  const go = () => {
    if (unread) read.mutate(a.id)
    if (a.link) navigate(a.link)
  }

  return (
    <li
      className={cn(
        'group relative flex items-start gap-4 overflow-hidden rounded-2xl border bg-card p-4 pl-5 transition-colors',
        unread ? 'shadow-sm' : 'bg-card/60',
        resolved && 'opacity-70',
      )}
    >
      <span className={cn('absolute inset-y-0 left-0 w-1', S.bar, !unread && 'opacity-40')} aria-hidden />
      <div className={cn('flex size-10 shrink-0 items-center justify-center rounded-xl', S.chip)}>
        <Icon className="size-5" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <p className={cn('font-medium', unread && 'font-semibold')}>{a.title}</p>
          {unread && <span className="size-2 rounded-full bg-primary" aria-label="Sin leer" />}
          {resolved && (
            <Badge variant="outline" className="border-success/40 text-success">
              Resuelta
            </Badge>
          )}
        </div>
        {a.message && <p className="mt-0.5 text-sm text-muted-foreground">{a.message}</p>}
        <p className="mt-1 text-xs text-muted-foreground" title={fmtDateTime(a.created_at)}>
          <span className="first-letter:uppercase">{fmtRelative(a.created_at)}</span>
          {resolved && a.resolved_at && ` · resuelta ${fmtRelative(a.resolved_at)}`}
        </p>
      </div>
      <div className="flex shrink-0 items-center gap-1">
        {unread && (
          <Tooltip>
            <TooltipTrigger asChild>
              <Button variant="ghost" size="icon" onClick={() => read.mutate(a.id)} aria-label="Marcar como leída">
                <Eye />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Marcar como leída</TooltipContent>
          </Tooltip>
        )}
        {!resolved && (
          <Tooltip>
            <TooltipTrigger asChild>
              <Button variant="ghost" size="icon" onClick={() => resolve.mutate(a.id)} aria-label="Resolver">
                <Check />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Resolver</TooltipContent>
          </Tooltip>
        )}
        {a.link && (
          <Button variant="outline" size="sm" onClick={go}>
            Ir <ArrowRight />
          </Button>
        )}
      </div>
    </li>
  )
}
