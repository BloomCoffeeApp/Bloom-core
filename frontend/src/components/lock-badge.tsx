import { Lock } from 'lucide-react'
import { Link } from 'react-router'

import { cn } from '@/lib/utils'

const TITLE = 'Bloqueado en el plan gratuito: se ve, pero no se puede usar. Elegí tus activos en Configuración.'

/** Lock + "Pro" chip for items the free plan keeps visible but not usable (backend `locked`). */
export function LockBadge({ className }: { className?: string }) {
  return (
    <span
      title={TITLE}
      data-testid="lock-badge"
      className={cn(
        'inline-flex shrink-0 items-center gap-1 rounded-full bg-warning/20 px-2 py-0.5 text-[11px] font-semibold text-warning-foreground dark:text-warning',
        className,
      )}
    >
      <Lock className="size-3" aria-hidden />
      Pro
    </span>
  )
}

/** Notice shown where a locked item is opened: what's allowed and where to change it. */
export function LockedNotice({ what, className }: { what: string; className?: string }) {
  return (
    <div
      role="status"
      className={cn(
        'flex items-start gap-2 rounded-xl border border-warning/40 bg-warning/10 p-3 text-sm text-warning-foreground dark:text-warning',
        className,
      )}
    >
      <Lock className="mt-0.5 size-4 shrink-0" aria-hidden />
      <p>
        {what} está bloqueado en el plan gratuito: se conserva con su historial, pero no se puede usar ni editar (solo
        archivar).{' '}
        <Link to="/config?tab=activos" className="font-medium underline underline-offset-2">
          Elegí tus activos
        </Link>{' '}
        o pasate a Pro.
      </p>
    </div>
  )
}
