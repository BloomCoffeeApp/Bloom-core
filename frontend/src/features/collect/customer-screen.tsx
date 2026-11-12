import { CircleCheckBig, CircleX, Coffee, Landmark, Loader2, MonitorX, Smartphone } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { fmtMoney } from '@/lib/format'

import { useScreenState } from './api'
import type { ScreenState } from './types'

/**
 * Customer-facing screen (tablet/TV on the local network): /pantalla-cliente?token=…
 * Shows the cart, the total and the QR (or the transfer details) of the charge the POS sends here.
 */
export default function CustomerScreenPage() {
  const token = new URLSearchParams(window.location.search).get('token') ?? ''
  const q = useScreenState(token)

  if (!token || (q.isError && !q.data))
    return (
      <Shell>
        <div className="flex flex-col items-center gap-4 text-center">
          <MonitorX className="size-16 text-muted-foreground" />
          <h1 className="font-heading text-3xl font-semibold">Pantalla no registrada</h1>
          <p className="max-w-md text-lg text-muted-foreground">
            {q.error?.message ?? 'Abrí el link de esta pantalla desde Configuración → Cobros en la caja.'}
          </p>
        </div>
      </Shell>
    )
  if (!q.data)
    return (
      <Shell>
        <Loader2 className="size-10 animate-spin text-primary" />
      </Shell>
    )
  return (
    <Shell>
      <ScreenBody s={q.data} />
    </Shell>
  )
}

function Shell({ children }: { children: React.ReactNode }) {
  return <main className="flex min-h-svh items-center justify-center bg-background p-4 text-foreground sm:p-8">{children}</main>
}

function ScreenBody({ s }: { s: ScreenState }) {
  const ch = s.charge
  if (s.state === 'idle' || !ch)
    return (
      <div className="flex flex-col items-center gap-5 text-center" data-testid="screen-idle">
        <div className="flex size-24 items-center justify-center rounded-3xl bg-primary/10">
          <Coffee className="size-12 text-primary" />
        </div>
        <h1 className="font-heading text-4xl font-semibold sm:text-6xl">{s.business_name || '¡Hola!'}</h1>
        <p className="text-xl text-muted-foreground">¡Gracias por tu visita!</p>
      </div>
    )
  if (s.state === 'approved')
    return (
      <div className="flex flex-col items-center gap-5 text-center" role="status" data-testid="screen-approved">
        <div className="flex size-36 items-center justify-center rounded-full bg-success/15 text-success">
          <CircleCheckBig className="size-20" />
        </div>
        <h1 className="font-heading text-5xl font-semibold sm:text-7xl">¡Pago aprobado!</h1>
        <p className="tabular text-2xl text-muted-foreground">{fmtMoney(ch.amount_cents)} · ¡Gracias!</p>
      </div>
    )
  if (s.state !== 'pending')
    return (
      <div className="flex flex-col items-center gap-4 text-center" role="status">
        <CircleX className="size-20 text-destructive" />
        <h1 className="font-heading text-4xl font-semibold">
          {s.state === 'rejected' ? 'El pago fue rechazado' : s.state === 'expired' ? 'El cobro venció' : 'Cobro cancelado'}
        </h1>
        <p className="text-xl text-muted-foreground">Consultá en la caja.</p>
      </div>
    )

  return (
    <div className="grid w-full max-w-6xl gap-6 lg:grid-cols-[1fr_1.1fr] lg:gap-10" data-testid="screen-pending">
      <section className="flex flex-col rounded-3xl border bg-card p-5 sm:p-7">
        <h2 className="font-heading text-2xl font-semibold">Tu compra</h2>
        <ul className="mt-4 flex-1 divide-y overflow-y-auto text-lg">
          {ch.items.map((it, i) => (
            <li key={i} className="flex items-baseline justify-between gap-4 py-2">
              <span className="min-w-0">
                <span className="tabular text-muted-foreground">{it.qty}×</span> {it.name}
              </span>
              <span className="tabular shrink-0">{fmtMoney(it.total_cents)}</span>
            </li>
          ))}
        </ul>
        <div className="mt-4 flex items-baseline justify-between border-t pt-4">
          <span className="text-xl">Total</span>
          <span className="tabular font-heading text-5xl font-semibold" data-testid="screen-total">
            {fmtMoney(ch.amount_cents)}
          </span>
        </div>
      </section>

      <section className="flex flex-col items-center justify-center gap-4 text-center">
        {ch.kind === 'transfer' && ch.transfer ? (
          <div className="w-full space-y-4 rounded-3xl border bg-card p-6">
            <Landmark className="mx-auto size-14 text-primary" />
            <p className="text-xl">Transferí a</p>
            {ch.transfer.alias && (
              <p className="font-mono text-3xl font-semibold break-all sm:text-4xl" data-testid="screen-alias">
                {ch.transfer.alias}
              </p>
            )}
            {ch.transfer.cbu && <p className="font-mono text-lg break-all text-muted-foreground">CBU/CVU {ch.transfer.cbu}</p>}
            {ch.transfer.holder && <p className="text-lg">{ch.transfer.holder}</p>}
            {ch.transfer.bank && <p className="text-muted-foreground">{ch.transfer.bank}</p>}
            <p className="text-muted-foreground">Mostrale el comprobante a quien te atiende.</p>
          </div>
        ) : ch.kind === 'point' ? (
          <div className="flex flex-col items-center gap-4">
            <Smartphone className="size-24 text-primary" />
            <p className="text-3xl font-semibold">Pagá en el posnet</p>
          </div>
        ) : (
          <>
            <p className="font-heading text-3xl font-semibold">Escaneá para pagar</p>
            {ch.qr_png && (
              <img
                src={ch.qr_png}
                alt="Código QR para pagar"
                className="aspect-square w-full max-w-[min(70vh,28rem)] rounded-3xl border bg-white p-3"
                data-testid="screen-qr"
              />
            )}
            <p className="max-w-md text-lg text-muted-foreground">
              Con Mercado Pago o la app de tu banco o billetera (MODO, Naranja X, Ualá y más).
            </p>
          </>
        )}
        <p className="flex items-center gap-2 text-muted-foreground">
          <Loader2 className="size-4 animate-spin" /> Esperando el pago…
        </p>
        {ch.fake && <Badge variant="outline">Modo de prueba: no se cobra de verdad</Badge>}
      </section>
    </div>
  )
}
