import { Check, Copy, FileUp, KeyRound, Loader2, RefreshCw, Sparkles, X } from 'lucide-react'
import { type ChangeEvent, useRef, useState } from 'react'
import { toast } from 'sonner'

import { ConfirmDialog } from '@/components/confirm-dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

import { SettingsCard } from '../settings/form'
import {
  hasFeature,
  type LicenseInfo,
  type ProFeature,
  useActivateLicense,
  useDeactivateLicense,
  useImportLicense,
  useLicense,
  useRefreshLicense,
  useStartTrial,
} from './api'
import { describePlan } from './describe-plan'
import { ProBadge } from './pro-gate'
import { CheckoutDialog, type CheckoutRef, SubscribeCard, SubscriptionCard } from './subscribe-card'

function PlanSummary({ info }: { info: LicenseInfo }) {
  const { title, detail } = describePlan(info)
  return (
    <div
      className={cn(
        'flex items-start gap-4 rounded-2xl border p-5',
        info.valid ? 'border-primary/30 bg-primary/5' : 'bg-muted/30',
      )}
    >
      <div
        className={cn(
          'flex size-12 shrink-0 items-center justify-center rounded-2xl',
          info.valid ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground',
        )}
      >
        <Sparkles className="size-6" />
      </div>
      <div className="min-w-0">
        <p className="font-heading text-xl font-semibold">{title}</p>
        <p className="text-sm text-muted-foreground">{detail}</p>
        {info.problem && <p className="mt-2 text-sm text-destructive">{info.problem}</p>}
      </div>
    </div>
  )
}

export function LicenseSection() {
  const { data: info, isLoading } = useLicense()
  const activate = useActivateLicense()
  const trial = useStartTrial()
  const importLic = useImportLicense()
  const refresh = useRefreshLicense()
  const deactivate = useDeactivateLicense()
  const [key, setKey] = useState('')
  const [confirmOff, setConfirmOff] = useState(false)
  const [checkout, setCheckout] = useState<CheckoutRef | null>(null)
  const [resumed, setResumed] = useState<string | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  if (isLoading || !info) return <Skeleton className="h-64 rounded-2xl" />

  // A purchase started earlier (e.g. the app was closed while paying) resumes its wait here.
  const shownCheckout: CheckoutRef | null =
    checkout ?? (info.pending_checkout && resumed !== info.pending_checkout ? { id: info.pending_checkout, url: null } : null)

  const onFile = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (file) importLic.mutate((await file.text()).trim())
  }
  const copyId = () => {
    void navigator.clipboard?.writeText(info.machine_id)
    toast.success('ID copiado')
  }
  const hasStored = info.valid || !!info.problem
  const busy = activate.isPending || trial.isPending || importLic.isPending

  return (
    <div className="space-y-6">
      <SettingsCard title="Licencia" description={`Tu plan de ${info.app_name} en esta computadora.`}>
        <PlanSummary info={info} />

        <div className="grid gap-2 sm:grid-cols-2">
          {(Object.entries(info.catalog) as [ProFeature, string][]).map(([feature, text]) => {
            const on = hasFeature(info, feature)
            return (
              <div key={feature} className="flex items-center gap-2 text-sm">
                {on ? <Check className="size-4 text-success" /> : <X className="size-4 text-muted-foreground" />}
                <span className={cn(!on && 'text-muted-foreground')}>{text}</span>
                {!on && <ProBadge className="ml-auto" />}
              </div>
            )
          })}
        </div>
        {!info.valid && (
          <p className="text-xs text-muted-foreground">
            Plan gratuito: hasta {info.free_limits.products} productos, {info.free_limits.stock_items} insumos,{' '}
            {info.free_limits.customers} clientes y {info.free_limits.users}{' '}
            {info.free_limits.users === 1 ? 'usuario' : 'usuarios'}; historial de ventas de los últimos{' '}
            {info.free_limits.sales_history_days} días.
          </p>
        )}
      </SettingsCard>

      {info.server_configured && (!info.valid || info.plan === 'trial') && <SubscribeCard proLabel={info.pro_label} onStarted={setCheckout} />}
      {info.server_configured && info.valid && info.plan === 'pro' && !info.perpetual && <SubscriptionCard />}

      {!(info.valid && info.perpetual) && (
        <SettingsCard
          title={info.valid ? 'Cambiar de licencia' : 'Ya tengo una clave'}
          description="Ingresá la clave que recibiste al suscribirte."
        >
          <form
            className="flex flex-col gap-2 sm:flex-row"
            onSubmit={(e) => {
              e.preventDefault()
              activate.mutate(key, { onSuccess: () => setKey('') })
            }}
          >
            <div className="relative flex-1">
              <KeyRound className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={key}
                onChange={(e) => setKey(e.target.value.toUpperCase())}
                placeholder="BLOOM-XXXXX-XXXXX-XXXXX-XXXXX"
                className="h-11 pl-9 font-mono"
                aria-label="Clave de licencia"
              />
            </div>
            <Button type="submit" className="h-11" disabled={key.trim().length < 8 || busy || !info.server_configured}>
              {activate.isPending && <Loader2 className="animate-spin" />} Activar
            </Button>
          </form>
          {!info.server_configured && (
            <p className="text-xs text-muted-foreground">
              Esta instalación no tiene servidor de licencias configurado: usá “Importar archivo de licencia”.
            </p>
          )}
          <div className="flex flex-wrap gap-2">
            {!hasStored && info.server_configured && (
              <Button variant="outline" onClick={() => trial.mutate(undefined)} disabled={busy}>
                <Sparkles /> Probar Pro 7 días gratis
              </Button>
            )}
            <Button variant="outline" onClick={() => fileRef.current?.click()} disabled={busy}>
              <FileUp /> Importar archivo de licencia
            </Button>
            <input ref={fileRef} type="file" accept=".lic,.txt" className="hidden" onChange={onFile} />
          </div>
        </SettingsCard>
      )}

      <SettingsCard title="Esta computadora" description="Para soporte o para pedir una licencia sin conexión a internet.">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline" className="h-9 px-3 font-mono text-xs">
            {info.machine_id}
          </Badge>
          <Button variant="ghost" size="sm" onClick={copyId}>
            <Copy /> Copiar ID
          </Button>
        </div>
        {hasStored && (
          <div className="flex flex-wrap gap-2">
            {info.server_configured && !info.perpetual && (
              <Button variant="outline" onClick={() => refresh.mutate(undefined)} disabled={refresh.isPending}>
                <RefreshCw className={cn(refresh.isPending && 'animate-spin')} /> Actualizar ahora
              </Button>
            )}
            <Button variant="ghost" className="text-destructive" onClick={() => setConfirmOff(true)}>
              Desactivar en esta PC
            </Button>
          </div>
        )}
      </SettingsCard>

      {shownCheckout && (
        <CheckoutDialog
          checkout={shownCheckout}
          onClose={() => {
            setResumed(shownCheckout.id)
            setCheckout(null)
          }}
        />
      )}

      <ConfirmDialog
        open={confirmOff}
        onOpenChange={setConfirmOff}
        title="¿Desactivar la licencia en esta computadora?"
        description="Libera el lugar para usarla en otra PC. Acá vuelve al plan gratuito; tus datos no se tocan."
        confirmLabel="Desactivar"
        destructive
        onConfirm={() => deactivate.mutate(undefined, { onSuccess: () => setConfirmOff(false) })}
      />
    </div>
  )
}
