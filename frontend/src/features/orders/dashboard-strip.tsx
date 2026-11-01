import { ChevronRight, ClipboardList } from 'lucide-react'
import { Link } from 'react-router'

import { cn } from '@/lib/utils'

import { fmtMinutes } from './timing'
import type { OrdersSummary } from './types'

/** Dashboard line of the order screen (free): late orders and average prep time in the period. */
export function OrdersStrip({ data, periodLabel }: { data: OrdersSummary | null | undefined; periodLabel: string }) {
  if (!data) return null
  return (
    <Link
      to="/pedidos"
      data-testid="orders-strip"
      className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-2xl border bg-card px-4 py-3 text-sm shadow-xs transition-colors hover:bg-muted/50"
    >
      <span className="flex items-center gap-2 font-medium">
        <span className="flex size-8 items-center justify-center rounded-xl bg-primary/10 text-primary">
          <ClipboardList className="size-4" />
        </span>
        Pedidos · <span className="first-letter:uppercase">{periodLabel.toLowerCase()}</span>
      </span>
      <span className={cn('font-semibold', data.late > 0 ? 'text-destructive' : 'text-success')}>
        {data.late} atrasado{data.late === 1 ? '' : 's'}
      </span>
      <span>
        promedio <span className="font-semibold tabular-nums">{fmtMinutes(data.avg_prep_s)}</span>
      </span>
      <span className="text-muted-foreground">
        {data.orders} terminado{data.orders === 1 ? '' : 's'}
        {data.open > 0 && ` · ${data.open} en curso`}
      </span>
      <ChevronRight className="ml-auto size-4 text-muted-foreground" />
    </Link>
  )
}
