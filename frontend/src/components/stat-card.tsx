import type { LucideIcon } from 'lucide-react'
import { TrendingDown, TrendingUp } from 'lucide-react'
import type { ReactNode } from 'react'

import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

export function StatCard({
  label,
  value,
  icon: Icon,
  hint,
  delta,
  loading,
  tone = 'default',
}: {
  label: string
  value: ReactNode
  icon?: LucideIcon
  hint?: ReactNode
  /** Percentage change vs. comparison period; positive = up. */
  delta?: number | null
  loading?: boolean
  tone?: 'default' | 'success' | 'warning' | 'danger'
}) {
  const toneCls = {
    default: 'bg-primary/10 text-primary',
    success: 'bg-success/15 text-success',
    warning: 'bg-warning/20 text-warning-foreground dark:text-warning',
    danger: 'bg-destructive/10 text-destructive',
  }[tone]
  return (
    <Card className="gap-0 py-0">
      <CardContent className="flex items-start justify-between gap-3 p-5">
        <div className="min-w-0 space-y-1">
          <p className="text-sm text-muted-foreground">{label}</p>
          {loading ? (
            <Skeleton className="h-8 w-28" />
          ) : (
            <p className="tabular truncate text-2xl font-semibold tracking-tight">{value}</p>
          )}
          {(delta != null || hint) && !loading && (
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              {delta != null && Number.isFinite(delta) && (
                <span
                  className={cn(
                    'inline-flex items-center gap-0.5 font-medium',
                    delta >= 0 ? 'text-success' : 'text-destructive',
                  )}
                >
                  {delta >= 0 ? <TrendingUp className="size-3" /> : <TrendingDown className="size-3" />}
                  {Math.abs(delta).toFixed(1)}%
                </span>
              )}
              {hint}
            </div>
          )}
        </div>
        {Icon && (
          <div className={cn('flex size-10 shrink-0 items-center justify-center rounded-xl', toneCls)}>
            <Icon className="size-5" />
          </div>
        )}
      </CardContent>
    </Card>
  )
}
