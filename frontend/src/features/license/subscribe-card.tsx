import { CircleCheckBig, Copy, ExternalLink, Loader2, Monitor, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

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
import { fmtMoney } from '@/lib/format'
import { cn } from '@/lib/utils'

import { SettingsCard } from '../settings/form'
import { type Plan, useCheckoutStatus, usePlans, useStartCheckout } from './api'

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
  const start = useStartCheckout()
  const [plan, setPlan] = useState<string | null>(null)
  const [email, setEmail] = useState('')

  if (plans.isLoading) return <Skeleton className="h-48 rounded-2xl" />
  if (!plans.data?.enabled) return null
  const entries = Object.entries(plans.data.plans)
  const selected = plan ?? entries[0]?.[0] ?? null

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
      <div className="flex flex-wrap items-center gap-3">
        <Button className="h-11" onClick={pay} disabled={!selected || !EMAIL_RE.test(email.trim()) || start.isPending}>
          {start.isPending && <Loader2 className="animate-spin" />} Pagar con Mercado Pago
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
