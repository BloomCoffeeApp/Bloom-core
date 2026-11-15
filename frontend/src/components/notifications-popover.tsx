import { useQuery } from '@tanstack/react-query'
import { Bell, BellRing, CheckCheck, ConciergeBell, Globe, Receipt, UtensilsCrossed } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { useAlertSummary, useAlerts, useReadAlert, useReadAll } from '@/features/alerts/api'
import type { Alert } from '@/features/alerts/types'
import { api } from '@/lib/api'
import { fmtRelative } from '@/lib/format'
import { cn } from '@/lib/utils'

interface UrgentItem {
  key: string
  kind: 'online_order' | 'table_order' | 'call_waiter' | 'call_bill'
  title: string
  detail: string | null
  at: string
  to: string
}

const URGENT_ICON = {
  online_order: Globe,
  table_order: UtensilsCrossed,
  call_waiter: ConciergeBell,
  call_bill: Receipt,
} as const

const SEVERITY_DOT: Record<string, string> = {
  critical: 'bg-destructive',
  warning: 'bg-warning',
  info: 'bg-info',
}

const MAX_ALERTS = 8

/** The header bell: «Ahora» (orders and tables waiting for you) and the latest alerts, in a popup. */
export function NotificationsPopover() {
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const summary = useAlertSummary()
  const urgent = useQuery({
    queryKey: ['notifications', 'urgent'],
    queryFn: () => api.get<{ items: UrgentItem[]; total: number }>('/notifications/urgent'),
    refetchInterval: 10_000,
  })
  const alerts = useAlerts('active')
  const readAlert = useReadAlert()
  const readAll = useReadAll()

  const openAlerts = summary.data?.open ?? 0
  const urgentItems = urgent.data?.items ?? []
  const total = openAlerts + (urgent.data?.total ?? 0)
  const critical = !!summary.data?.critical || urgentItems.some((i) => i.kind === 'call_bill' || i.kind === 'call_waiter')
  const list = (alerts.data ?? []).slice(0, MAX_ALERTS)

  const go = (to: string) => {
    setOpen(false)
    navigate(to)
  }
  const openAlert = (a: Alert) => {
    if (a.status === 'open') readAlert.mutate(a.id)
    go(a.link || '/avisos')
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="ghost" size="icon" className="relative" data-tour="alerts" aria-label={total ? `Notificaciones: ${total}` : 'Notificaciones'}>
          {urgentItems.length ? <BellRing /> : <Bell />}
          {!!total && (
            <Badge className={cn('absolute -top-1 -right-1 h-4 min-w-4 rounded-full px-1 text-[10px]', critical ? 'bg-destructive text-white' : '')}>
              {total > 99 ? '99+' : total}
            </Badge>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-[min(24rem,calc(100vw-1.5rem))] gap-0 p-0" data-testid="notifications-popover">
        <div className="flex items-center justify-between gap-2 px-3 py-2.5">
          <p className="font-heading text-base font-semibold">Notificaciones</p>
          {openAlerts > 0 && (
            <Button variant="ghost" size="sm" className="h-8 gap-1.5 text-xs" disabled={readAll.isPending} onClick={() => readAll.mutate()}>
              <CheckCheck className="size-3.5" /> Marcar todas como leídas
            </Button>
          )}
        </div>

        <div className="max-h-[min(28rem,70svh)] overflow-y-auto border-t">
          {urgentItems.length > 0 && (
            <section aria-label="Ahora" className="p-1.5">
              <p className="px-2 pt-1 pb-1.5 text-xs font-semibold tracking-wide text-muted-foreground uppercase">Ahora</p>
              {urgentItems.map((i) => {
                const Icon = URGENT_ICON[i.kind]
                return (
                  <button
                    key={i.key}
                    type="button"
                    onClick={() => go(i.to)}
                    className="flex min-h-12 w-full items-center gap-3 rounded-lg px-2 py-1.5 text-left outline-none hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                      <Icon className="size-4.5" />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium">{i.title}</span>
                      <span className="block truncate text-xs text-muted-foreground">
                        {i.detail ? `${i.detail} · ` : ''}
                        {fmtRelative(i.at)}
                      </span>
                    </span>
                  </button>
                )
              })}
            </section>
          )}

          <section aria-label="Alertas" className={cn('p-1.5', urgentItems.length > 0 && 'border-t')}>
            <p className="px-2 pt-1 pb-1.5 text-xs font-semibold tracking-wide text-muted-foreground uppercase">Alertas</p>
            {list.length === 0 ? (
              <p className="px-2 py-4 text-center text-sm text-muted-foreground">{urgentItems.length ? 'Sin alertas.' : 'Todo en orden. No hay nada pendiente.'}</p>
            ) : (
              list.map((a) => (
                <button
                  key={a.id}
                  type="button"
                  onClick={() => openAlert(a)}
                  className="flex min-h-12 w-full items-start gap-3 rounded-lg px-2 py-2 text-left outline-none hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <span aria-hidden className={cn('mt-1.5 size-2.5 shrink-0 rounded-full', SEVERITY_DOT[a.severity] ?? 'bg-muted-foreground', a.status !== 'open' && 'opacity-30')} />
                  <span className="min-w-0 flex-1">
                    <span className={cn('block text-sm', a.status === 'open' ? 'font-medium' : 'text-muted-foreground')}>{a.title}</span>
                    {a.message && <span className="line-clamp-2 text-xs text-muted-foreground">{a.message}</span>}
                    <span className="block text-xs text-muted-foreground/80">{fmtRelative(a.created_at)}</span>
                  </span>
                </button>
              ))
            )}
          </section>
        </div>

        <div className="border-t p-1.5">
          <Button asChild variant="ghost" className="h-10 w-full justify-center text-sm" onClick={() => setOpen(false)}>
            <Link to="/avisos">Ver todas</Link>
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  )
}
