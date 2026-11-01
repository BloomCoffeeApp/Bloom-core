import { TrendingUp } from 'lucide-react'
import { Link } from 'react-router'

import { useAuth } from '@/lib/auth'
import { fmtDate, fmtMoney } from '@/lib/format'

import { useLicense } from './api'
import { LICENSE_TAB } from './pro-gate'

/** Admins see this until they accept the new price or cancel (the backend remembers the last status). */
export function PriceChangeBanner() {
  const { data } = useLicense()
  const { can } = useAuth()
  const change = data?.pending_price_change
  if (!can() || !change || change.accepted) return null
  return (
    <div className="flex items-center gap-2 border-b bg-warning/15 px-4 py-2 text-sm" data-testid="price-change-banner">
      <TrendingUp className="size-4 shrink-0" />
      <span className="flex-1">
        Desde el {fmtDate(change.effective_at)} tu suscripción pasa a{' '}
        <b className="tabular">{fmtMoney(change.new_amount_cents)}</b>. Aceptalo o cancelala antes de esa fecha.
      </span>
      <Link to={LICENSE_TAB} className="font-medium text-primary hover:underline">
        Revisar
      </Link>
    </div>
  )
}
