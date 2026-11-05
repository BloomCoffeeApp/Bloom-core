import {
  BadgeCheck,
  CircleCheckBig,
  CircleSlash,
  Copy,
  ExternalLink,
  Loader2,
  Monitor,
  Repeat,
  ShieldCheck,
  TrendingUp,
} from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { ConfirmDialog } from '@/components/confirm-dialog'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { fmtDate, fmtMoney } from '@/lib/format'
import { cn } from '@/lib/utils'

import { useBusinessModules } from '../business/api'
import { SettingsCard } from '../settings/form'
import {
  type Plan,
  type PriceChange,
  useAcceptPrice,
  useCancelSubscription,
  useCheckoutStatus,
  usePlans,
  useStartCheckout,
  useSubscription,
} from './api'

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/

function period(p: Plan) {
  if (p.frequency_type === 'months' && p.frequency === 12) return 'por año'
  if (p.frequency_type === 'months' && p.frequency === 1) return 'por mes'
  return `cada ${p.frequency} ${p.frequency_type === 'months' ? 'meses' : 'días'}`
}

/** Subscribe from the app: pay in Mercado Pago, the license activates itself. */
export type CheckoutRef = { id: string; url: string | null }

export function SubscribeCard({ proLabel, onStarted }: { proLabel: string; onStarted: (c: CheckoutRef) => void }) {
  const plans = usePlans(true)
  const business = useBusinessModules()
  const start = useStartCheckout()
  const [plan, setPlan] = useState<string | null>(null)
  const [email, setEmail] = useState('')

  if (plans.isLoading) return <Skeleton className="h-48 rounded-2xl" />
  if (!plans.data?.enabled) return null
  // Plans recommended for this business type go first (stable: the server's order otherwise).
  const profile = business.data?.profile
  const fits = (p: Plan) => !!profile && !!p.profiles?.includes(profile)
  const entries = Object.entries(plans.data.plans).sort(([, a], [, b]) => Number(fits(b)) - Number(fits(a)))
  const profileLabel = business.data?.profiles.find((x) => x.key === profile)?.label
  const selected = plan ?? entries[0]?.[0] ?? null
  const chosen = selected ? plans.data.plans[selected] : null

  const pay = () => {
    if (!selected) return
    start.mutate(
      { plan: selected, email: email.trim() },
      {
        onSuccess: (r) => {
          onStarted({ id: r.checkout_id, url: r.url })
          window.open(r.url, '_blank', 'noopener')
        },
      },
    )
  }

  return (
    <SettingsCard
      title={`Suscribite a ${proLabel}`}
      description="Pagás con tarjeta en Mercado Pago y se renueva solo. Podés cancelarlo cuando quieras desde tu cuenta de Mercado Pago."
    >
      <div className="grid gap-3 sm:grid-cols-3" role="radiogroup" aria-label="Plan">
        {entries.map(([key, p]) => (
          <button
            key={key}
            type="button"
            role="radio"
            aria-checked={selected === key}
            onClick={() => setPlan(key)}
            className={cn(
              'flex min-h-28 flex-col items-start gap-1 rounded-2xl border p-4 text-left transition-colors',
              selected === key ? 'border-primary bg-primary/5 ring-2 ring-primary/30' : 'hover:bg-muted/50',
            )}
          >
            {fits(p) && (
              <span className="rounded-full bg-primary px-2 py-0.5 text-[11px] font-medium text-primary-foreground" data-testid="plan-recommended">
                Recomendado{profileLabel ? ` para ${profileLabel.toLowerCase()}` : ''}
              </span>
            )}
            <span className="font-medium">{p.label}</span>
            <span className="font-heading text-2xl font-semibold tabular">{fmtMoney(p.amount_cents, { short: true })}</span>
            <span className="text-xs text-muted-foreground">{period(p)}</span>
            {p.description && <span className="mt-1 text-xs text-muted-foreground">{p.description}</span>}
            <span className="mt-auto flex items-center gap-1 pt-1 text-xs text-muted-foreground">
              <Monitor className="size-3" /> {p.devices} {p.devices === 1 ? 'computadora' : 'computadoras'}
            </span>
          </button>
        ))}
      </div>
      <div className="grid gap-1.5 sm:max-w-sm">
        <Label htmlFor="sub-email">Email para la factura y la clave</Label>
        <Input
          id="sub-email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="tu@email.com"
          className="h-11"
        />
      </div>
      {chosen && (
        <p className="flex items-start gap-2 rounded-xl border border-primary/30 bg-primary/5 p-3 text-sm" data-testid="auto-charge-notice">
          <Repeat className="mt-0.5 size-4 shrink-0 text-primary" />
          <span>
            <b>Es una suscripción con cobro automático:</b> se debitan{' '}
            <b className="tabular">{fmtMoney(chosen.amount_cents)}</b> {period(chosen)} de tu tarjeta hasta que la
            canceles desde tu cuenta de Mercado Pago (Suscripciones). Lo que ya pagaste sigue funcionando hasta que
            termine el período.
          </span>
        </p>
      )}
      <div className="flex flex-wrap items-center gap-3">
        <Button className="h-11" onClick={pay} disabled={!selected || !EMAIL_RE.test(email.trim()) || start.isPending}>
          {start.isPending && <Loader2 className="animate-spin" />} Suscribirme con Mercado Pago
        </Button>
        <span className="flex items-center gap-1 text-xs text-muted-foreground">
          <ShieldCheck className="size-3.5" /> Los datos de tu tarjeta los maneja Mercado Pago, nunca pasan por esta app.
        </span>
      </div>
    </SettingsCard>
  )
}

/** Waits for Mercado Pago; lives outside SubscribeCard so it survives the switch to Pro. */
export function CheckoutDialog({ checkout, onClose }: { checkout: CheckoutRef; onClose: () => void }) {
  const status = useCheckoutStatus(checkout.id)
  const done = status.data?.status === 'authorized' && !!status.data.license
  const cancelled = status.data?.status === 'cancelled'
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-md">
        {done ? (
          <>
            <DialogHeader className="items-center text-center">
              <div className="flex size-16 items-center justify-center rounded-full bg-success/15 text-success">
                <CircleCheckBig className="size-9" />
              </div>
              <DialogTitle className="font-heading text-2xl">¡Listo, ya tenés Pro!</DialogTitle>
              <DialogDescription>
                Se activó en esta computadora. Guardá tu clave para activarlo en otra PC de tu plan:
              </DialogDescription>
            </DialogHeader>
            <div className="flex items-center gap-2 rounded-xl border bg-muted/40 p-3 font-mono text-sm">
              <span className="flex-1 break-all">{status.data?.key}</span>
              <Button
                variant="ghost"
                size="icon"
                aria-label="Copiar clave"
                onClick={() => {
                  void navigator.clipboard?.writeText(status.data?.key ?? '')
                  toast.success('Clave copiada')
                }}
              >
                <Copy />
              </Button>
            </div>
            <DialogFooter>
              <Button className="h-11 w-full" onClick={onClose}>
                Empezar a usar Pro
              </Button>
            </DialogFooter>
          </>
        ) : (
          <>
            <DialogHeader>
              <DialogTitle>{cancelled ? 'La suscripción se canceló' : 'Esperando el pago…'}</DialogTitle>
              <DialogDescription>
                {cancelled
                  ? 'Mercado Pago no completó la suscripción. Podés intentarlo de nuevo.'
                  : 'Completá el pago en la ventana de Mercado Pago. Cuando se apruebe, Pro se activa solo acá.'}
              </DialogDescription>
            </DialogHeader>
            {!cancelled && (
              <div className="flex items-center justify-center py-4 text-muted-foreground">
                <Loader2 className="size-8 animate-spin" />
              </div>
            )}
            {status.error && (
              <p className="rounded-xl bg-warning/15 p-3 text-sm">
                {status.error.message} Seguimos intentando; si no se resuelve, escribinos con el ID de esta computadora.
              </p>
            )}
            <DialogFooter className="gap-2 sm:justify-between">
              <Button variant="ghost" onClick={onClose}>
                Cerrar
              </Button>
              {checkout.url && (
                <Button variant="outline" asChild>
                  <a href={checkout.url} target="_blank" rel="noopener noreferrer">
                    <ExternalLink /> Abrir Mercado Pago
                  </a>
                </Button>
              )}
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}

/** A new price announced by the vendor: accept it, or the subscription ends on that date. */
function PriceChangeNotice({ change, every, onCancel }: { change: PriceChange; every: string; onCancel: () => void }) {
  const accept = useAcceptPrice()
  const [confirm, setConfirm] = useState(false)
  const from = fmtDate(change.effective_at)
  if (change.accepted) {
    return (
      <p className="flex items-start gap-2 rounded-xl border bg-muted/40 p-3 text-sm" data-testid="price-change">
        <BadgeCheck className="mt-0.5 size-4 shrink-0 text-success" />
        <span>
          {change.needs_acceptance ? 'Aceptaste el nuevo precio: ' : 'Baja el precio: '}
          desde el {from} se debitan <b className="tabular">{fmtMoney(change.new_amount_cents)}</b> {every}.
        </span>
      </p>
    )
  }
  return (
    <div className="space-y-3 rounded-xl border border-warning/40 bg-warning/10 p-3 text-sm" data-testid="price-change">
      <p className="flex items-start gap-2">
        <TrendingUp className="mt-0.5 size-4 shrink-0" />
        <span>
          <b>Cambia el precio de tu suscripción.</b> Desde el {from} pasa de{' '}
          <span className="tabular">{fmtMoney(change.old_amount_cents)}</span> a{' '}
          <b className="tabular">{fmtMoney(change.new_amount_cents)}</b> {every}. Si no lo aceptás antes de esa fecha no se
          te cobra el precio nuevo: la suscripción se cancela sola y Pro sigue hasta el final del período que ya pagaste.
        </span>
      </p>
      <div className="flex flex-wrap gap-2">
        <Button className="h-11" onClick={() => setConfirm(true)} disabled={accept.isPending}>
          {accept.isPending && <Loader2 className="animate-spin" />} Aceptar nuevo precio
        </Button>
        <Button variant="outline" className="h-11 text-destructive hover:text-destructive" onClick={onCancel}>
          <CircleSlash /> Cancelar suscripción
        </Button>
      </div>
      <ConfirmDialog
        open={confirm}
        onOpenChange={setConfirm}
        title="¿Aceptar el nuevo precio?"
        description={`Desde el ${from} se van a debitar ${fmtMoney(change.new_amount_cents)} ${every} de tu tarjeta. Podés cancelar la suscripción cuando quieras, sin costo.`}
        confirmLabel="Aceptar"
        onConfirm={() =>
          accept.mutate(undefined, {
            onSuccess: () => {
              setConfirm(false)
              toast.success('Listo, aceptaste el nuevo precio.')
            },
          })
        }
      />
    </div>
  )
}

/** The subscription behind a paid license, with a visible way to cancel it ("botón de baja"). */
export function SubscriptionCard() {
  const sub = useSubscription(true)
  const cancel = useCancelSubscription()
  const [confirm, setConfirm] = useState(false)
  if (sub.isLoading) return <Skeleton className="h-32 rounded-2xl" />
  if (sub.isError)
    return (
      <SettingsCard title="Tu suscripción" description="No pudimos consultar tu suscripción ahora.">
        <p className="text-sm text-muted-foreground">
          {sub.error.message} También podés cancelarla desde tu cuenta de Mercado Pago (Suscripciones).
        </p>
      </SettingsCard>
    )
  const s = sub.data
  if (!s?.has_subscription) return null
  const until = fmtDate(s.paid_through)
  const cancelled = s.status === 'cancelled'
  const every = s.days && s.days >= 365 ? 'por año' : 'por mes'
  return (
    <SettingsCard
      title="Tu suscripción"
      description={cancelled ? 'Cancelada: no se te va a volver a cobrar.' : 'Se cobra sola con tu tarjeta en Mercado Pago.'}
    >
      <div className="grid gap-1 text-sm">
        <p>
          <b>{s.plan_label}</b>
          {s.amount_cents != null && (
            <>
              {' '}
              · <span className="tabular">{fmtMoney(s.amount_cents)}</span> {every}
            </>
          )}
        </p>
        <p className="text-muted-foreground">
          {cancelled ? `Pro sigue activo hasta el ${until}, que ya está pago.` : `Pagado hasta el ${until}; después se renueva sola.`}
        </p>
      </div>
      {cancelled ? (
        <p className="flex items-start gap-2 rounded-xl border bg-muted/40 p-3 text-sm" data-testid="cancellation-code">
          <CircleSlash className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
          <span>
            Código de baja: <b className="font-mono">{s.cancellation_code}</b>. Te lo mandamos también por mail. Si
            querés volver, suscribite de nuevo cuando quieras.
          </span>
        </p>
      ) : s.pending_price_change && !s.pending_price_change.accepted ? (
        <PriceChangeNotice change={s.pending_price_change} every={every} onCancel={() => setConfirm(true)} />
      ) : (
        <>
          {s.pending_price_change && <PriceChangeNotice change={s.pending_price_change} every={every} onCancel={() => setConfirm(true)} />}
          <div>
            <Button variant="outline" className="h-11 text-destructive hover:text-destructive" onClick={() => setConfirm(true)}>
              <CircleSlash /> Cancelar suscripción
            </Button>
          </div>
        </>
      )}
      <ConfirmDialog
        open={confirm}
        onOpenChange={setConfirm}
        title="¿Cancelar la suscripción?"
        description={`No se van a hacer más débitos. Lo que ya pagaste sigue funcionando hasta el ${until}; después la app vuelve al plan gratuito sin perder tus datos.`}
        confirmLabel="Sí, cancelar"
        destructive
        onConfirm={() =>
          cancel.mutate(undefined, {
            onSuccess: (r) => {
              setConfirm(false)
              toast.success(`Suscripción cancelada. Código de baja: ${r.cancellation_code}`)
            },
          })
        }
      />
    </SettingsCard>
  )
}
