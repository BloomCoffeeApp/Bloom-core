import { Lock } from 'lucide-react'
import { Link } from 'react-router'

import { useAuth } from '@/lib/auth'
import { cn } from '@/lib/utils'

import { type FreeKind, useFreePlan } from './api'

const NOUN: Record<FreeKind, [string, string]> = {
  products: ['producto bloqueado', 'productos bloqueados'],
  customers: ['cliente bloqueado', 'clientes bloqueados'],
  stock_items: ['insumo bloqueado', 'insumos bloqueados'],
  users: ['usuario bloqueado', 'usuarios bloqueados'],
}

/** "N productos bloqueados por el plan gratuito" + link to "Elegí tus activos" (nothing when Pro). */
export function FreeLocksBanner({ kinds, className }: { kinds: FreeKind[]; className?: string }) {
  const { data } = useFreePlan()
  const { can } = useAuth()
  if (!data) return null
  const parts = kinds
    .map((k) => data.kinds[k])
    .filter((s) => s.limited && s.locked > 0)
    .map((s) => `${s.locked} ${NOUN[s.kind][s.locked === 1 ? 0 : 1]}`)
  if (!parts.length) return null
  return (
    <div
      role="status"
      data-testid="free-locks-banner"
      className={cn(
        'flex flex-wrap items-center gap-2 rounded-xl border border-warning/40 bg-warning/10 px-3 py-2 text-sm text-warning-foreground dark:text-warning',
        className,
      )}
    >
      <Lock className="size-4 shrink-0" aria-hidden />
      <span>
        Plan gratuito: {parts.join(', ')}. Se ven y conservan su historial, pero no se pueden usar.
      </span>
      {can() && (
        <Link to="/config?tab=activos" className="ml-auto font-medium underline underline-offset-2">
          Elegí tus activos
        </Link>
      )}
    </div>
  )
}
