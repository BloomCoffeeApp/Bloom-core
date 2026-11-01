import { AlertTriangle, Check, Sparkles } from 'lucide-react'
import { useState } from 'react'
import type { ComponentType, LazyExoticComponent, ReactNode } from 'react'
import { Link, useNavigate } from 'react-router'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { useAuth } from '@/lib/auth'
import { cn } from '@/lib/utils'

import { type ProFeature, useHasFeature, useLicense } from './api'

export const LICENSE_TAB = '/config?tab=licencia'

export function ProBadge({ className }: { className?: string }) {
  return (
    <Badge className={cn('h-5 gap-1 border-primary/30 bg-primary/10 px-1.5 text-[10px] font-semibold text-primary', className)}>
      <Sparkles className="size-3!" /> Pro
    </Badge>
  )
}

/** Renders children only when the feature is licensed; otherwise a friendly upgrade card. */
export function ProGate({ feature, children }: { feature: ProFeature; children: ReactNode }) {
  const allowed = useHasFeature(feature)
  if (allowed === undefined) return null
  return allowed ? <>{children}</> : <UpgradeCard feature={feature} />
}

/** A Pro module: missing from this build (Free edition) or not licensed → upgrade card. */
export function ProModule({
  feature,
  component: Component,
}: {
  feature: ProFeature
  component?: LazyExoticComponent<ComponentType>
}) {
  if (!Component) return <UpgradeCard feature={feature} notIncluded />
  return (
    <ProGate feature={feature}>
      <Component />
    </ProGate>
  )
}

export function UpgradeCard({
  feature,
  compact = false,
  notIncluded = false,
}: {
  feature: ProFeature
  compact?: boolean
  /** The module isn't part of this build (Free edition). */
  notIncluded?: boolean
}) {
  const { data } = useLicense()
  const { can } = useAuth()
  if (!data) return null
  if (notIncluded && data.valid) {
    return (
      <div className={cn('mx-auto max-w-2xl', compact ? 'py-2' : 'py-10')}>
        <div className="rounded-3xl border bg-card p-6 text-center shadow-sm sm:p-8">
          <Sparkles className="mx-auto size-8 text-primary" />
          <h2 className="mt-3 font-heading text-2xl font-semibold">{data.catalog[feature]}</h2>
          <p className="mt-2 text-muted-foreground">
            Tu licencia incluye esta función, pero esta instalación es la edición gratuita. Instalá {data.pro_label}{' '}
            para usarla.
          </p>
        </div>
      </div>
    )
  }
  const label = data.catalog[feature]
  return (
    <div className={cn('mx-auto max-w-2xl', compact ? 'py-2' : 'py-10')}>
      <div className="rounded-3xl border bg-card p-6 shadow-sm sm:p-8">
        <div className="flex items-center gap-3">
          <div className="flex size-12 items-center justify-center rounded-2xl bg-primary/10 text-primary">
            <Sparkles className="size-6" />
          </div>
          <div>
            <p className="text-sm font-medium text-primary">{data.pro_label}</p>
            <h2 className="font-heading text-2xl font-semibold">{label}</h2>
          </div>
        </div>
        {data.problem && (
          <p className="mt-4 flex items-start gap-2 rounded-xl bg-warning/15 p-3 text-sm">
            <AlertTriangle className="mt-0.5 size-4 shrink-0" />
            {data.problem}
          </p>
        )}
        <p className="mt-4 text-muted-foreground">
          Esta función es parte de {data.pro_label}. Tus datos y todo lo que ya usás siguen funcionando igual; con Pro
          sumás:
        </p>
        <ul className="mt-4 grid gap-2 sm:grid-cols-2">
          {Object.entries(data.catalog).map(([key, text]) => (
            <li key={key} className={cn('flex items-start gap-2 text-sm', key === feature && 'font-medium')}>
              <Check className="mt-0.5 size-4 shrink-0 text-success" />
              {text}
            </li>
          ))}
        </ul>
        <div className="mt-6 flex flex-wrap gap-2">
          {can() ? (
            <Button asChild className="h-11">
              <Link to={LICENSE_TAB}>
                <Sparkles /> Activar {data.pro_label}
              </Link>
            </Button>
          ) : (
            <p className="text-sm text-muted-foreground">Pedile al administrador que active {data.pro_label}.</p>
          )}
        </div>
      </div>
    </div>
  )
}

/** Thin banner when a trial/subscription is about to end, is in grace, or has a problem. */
export function LicenseBanner() {
  const { data } = useLicense()
  const { can } = useAuth()
  if (!data) return null
  let text: string | null = null
  let urgent = false
  if (data.valid && data.in_grace) {
    text = `Tu suscripción venció. Las funciones Pro siguen activas ${data.days_left} día(s) más mientras se renueva.`
    urgent = true
  } else if (data.valid && data.plan === 'trial' && (data.days_left ?? 99) <= 3) {
    text =
      data.days_left === 1
        ? `Mañana termina tu prueba de ${data.pro_label}. Suscribite para no perder las funciones Pro.`
        : `Te quedan ${data.days_left} días de prueba de ${data.pro_label}.`
    urgent = (data.days_left ?? 99) <= 1
  } else if (data.valid && !data.perpetual && data.plan === 'pro' && (data.days_left ?? 99) <= 3) {
    text = `Tu suscripción se renueva en ${data.days_left} día(s).`
  } else if (!data.valid && data.problem && !data.trial_ended) {
    text = data.problem
    urgent = true
  }
  if (!text) return null
  return (
    <div
      className={cn(
        'flex items-center gap-2 border-b px-4 py-2 text-sm',
        urgent ? 'bg-warning/15 text-foreground' : 'bg-primary/10 text-foreground',
      )}
    >
      <AlertTriangle className="size-4 shrink-0" />
      <span className="flex-1">{text}</span>
      {can() && (
        <Link to={LICENSE_TAB} className="font-medium text-primary hover:underline">
          Ver licencia
        </Link>
      )}
    </div>
  )
}

const trialSeenKey = (id: string | null) => `bloom.trial-ended-seen.${id ?? 'local'}`

function seenTrialEnd(id: string | null) {
  try {
    return localStorage.getItem(trialSeenKey(id)) === '1'
  } catch {
    return false
  }
}

/** Once, when the Pro trial runs out: offer to subscribe or keep the free plan. */
export function TrialEndedDialog() {
  const { data } = useLicense()
  const { can } = useAuth()
  const navigate = useNavigate()
  const [closed, setClosed] = useState(false)
  if (!data?.trial_ended || data.valid || closed || seenTrialEnd(data.license_id)) return null
  const close = () => {
    try {
      localStorage.setItem(trialSeenKey(data.license_id), '1')
    } catch {
      /* private mode: it just shows again next time */
    }
    setClosed(true)
  }
  const admin = can()
  return (
    <Dialog open onOpenChange={(o) => !o && close()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="font-heading text-2xl">Terminó tu prueba de {data.pro_label}</DialogTitle>
          <DialogDescription>
            Tus datos quedan intactos. Seguís con el plan gratuito: punto de venta, caja, stock y clientes, con
            hasta {data.free_limits.products} productos y {data.free_limits.customers} clientes. Barista, compras,
            reportes, menú para clientes y modo red local quedan bloqueados.
          </DialogDescription>
        </DialogHeader>
        {!admin && <p className="text-sm text-muted-foreground">Pedile al administrador que active {data.pro_label}.</p>}
        <DialogFooter className="gap-2 sm:justify-between">
          <Button variant="ghost" className="h-11" onClick={close}>
            Seguir con el plan gratis
          </Button>
          {admin && (
            <Button
              className="h-11"
              onClick={() => {
                close()
                void navigate(LICENSE_TAB)
              }}
            >
              <Sparkles /> Suscribirme a Pro
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
