import { PiggyBank, TrendingDown, TrendingUp } from 'lucide-react'
import { Link } from 'react-router'

import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { fmtMoney, fmtPct } from '@/lib/format'
import { cn } from '@/lib/utils'

import { useNow } from '@/hooks/use-now'

import { useMonthResult } from './api'
import { currentMonth } from './utils'

/** Inicio: "Ganancia real del mes" = ventas − costo de mercadería − cortesías/mermas − gastos (Free). */
export function ProfitCard() {
  const month = currentMonth(useNow())
  const res = useMonthResult(month)
  const c = res.data?.current
  const p = res.data?.previous
  const delta = c && p && p.profit_cents ? ((c.profit_cents - p.profit_cents) * 100) / Math.abs(p.profit_cents) : null
  return (
    <Card className="gap-0 py-0" data-testid="profit-card">
      <CardContent className="space-y-3 p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 space-y-1">
            <p className="text-sm text-muted-foreground">Ganancia real del mes</p>
            {res.isLoading || !c ? (
              <Skeleton className="h-8 w-32" />
            ) : (
              <p className={cn('tabular text-2xl font-semibold tracking-tight', c.profit_cents < 0 && 'text-destructive')}>
                {fmtMoney(c.profit_cents)}
              </p>
            )}
          </div>
          <div className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-success/15 text-success">
            <PiggyBank className="size-5" />
          </div>
        </div>
        {c && (
          <>
            <div className="space-y-0.5 text-xs text-muted-foreground">
              <div className="flex justify-between">
                <span>Ventas − costo</span>
                <span className="tabular">{fmtMoney(c.gross_margin_cents)}</span>
              </div>
              <div className="flex justify-between">
                <span>Cortesías y mermas</span>
                <span className="tabular">−{fmtMoney(c.losses_cents)}</span>
              </div>
              <div className="flex justify-between">
                <span>
                  Gastos
                  {c.expenses_pending_cents ? ` (${fmtMoney(c.expenses_pending_cents, { short: true })} pendientes)` : ''}
                </span>
                <span className="tabular">−{fmtMoney(c.expenses_cents)}</span>
              </div>
              {!!c.expenses_upcoming_cents && (
                <div className="flex justify-between">
                  <span>Faltan este mes</span>
                  <span className="tabular">{fmtMoney(c.expenses_upcoming_cents)}</span>
                </div>
              )}
            </div>
            <div className="flex items-center justify-between gap-2 text-xs">
              {delta != null ? (
                <span className={cn('inline-flex items-center gap-0.5 font-medium', delta >= 0 ? 'text-success' : 'text-destructive')}>
                  {delta >= 0 ? <TrendingUp className="size-3" /> : <TrendingDown className="size-3" />}
                  {fmtPct(Math.abs(delta))} vs el mes pasado
                </span>
              ) : (
                <span className="text-muted-foreground">{res.data?.partial ? 'Mes en curso' : ''}</span>
              )}
              <Link to="/gastos" className="font-medium text-primary underline-offset-4 hover:underline">
                Ver gastos
              </Link>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  )
}
