import { CircleCheckBig, CircleX, Landmark, Loader2, Monitor, MonitorOff, QrCode, RotateCw, Smartphone, TabletSmartphone } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { fmtMoney } from '@/lib/format'
import { cn } from '@/lib/utils'

import type { SaleDetail, SaleIn } from '../sales/types'
import { useCharge, useChargeAction, useCollectStatus, useCreatePosCharge } from './api'
import type { Charge, CollectMethod, CollectStatus } from './types'

const SCREEN_KEY = 'bloom.collect.screen'

function rememberedScreen(status: CollectStatus | undefined): number | null {
  let saved: string | null = null
  try {
    saved = localStorage.getItem(SCREEN_KEY)
  } catch {
    /* storage unavailable */
  }
  const ids = status?.screens.map((s) => s.id) ?? []
  if (saved === 'none') return null
  if (saved && ids.includes(Number(saved))) return Number(saved)
  if (status?.default_screen_id && ids.includes(status.default_screen_id)) return status.default_screen_id
  return ids[0] ?? null
}

function remember(id: number | null) {
  try {
    localStorage.setItem(SCREEN_KEY, id == null ? 'none' : String(id))
  } catch {
    /* storage unavailable */
  }
}

const TITLES: Record<CollectMethod, string> = {
  mp_qr: 'Cobro con QR',
  mp_point: 'Cobro con Point',
  transferencia: 'Cobro por transferencia',
}

function useCountdown(until: string | null) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(t)
  }, [])
  if (!until) return null
  const ms = new Date(until.endsWith('Z') ? until : `${until}Z`).getTime() - now
  if (ms <= 0) return '0:00'
  const s = Math.floor(ms / 1000)
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

function ScreenPicker({ status, value, onChange }: { status: CollectStatus; value: number | null; onChange: (id: number | null) => void }) {
  const options = [{ id: null as number | null, name: 'Solo en esta caja' }, ...status.screens]
  return (
    <div className="space-y-2">
      <p className="text-sm font-medium">¿En qué pantalla lo ve el cliente?</p>
      <div className="flex flex-wrap gap-2">
        {options.map((o) => {
          const on = value === o.id
          const Icon = o.id == null ? MonitorOff : Monitor
          return (
            <button
              key={o.id ?? 'none'}
              type="button"
              onClick={() => onChange(o.id)}
              aria-pressed={on}
              className={cn(
                'flex min-h-12 items-center gap-2 rounded-xl border px-4 text-sm font-medium transition-colors',
                on ? 'border-primary bg-primary text-primary-foreground' : 'bg-card hover:bg-muted',
              )}
            >
              <Icon className="size-4" /> {o.name}
            </button>
          )
        })}
      </div>
      {status.screens.length === 0 && (
        <p className="text-xs text-muted-foreground">Podés sumar una tablet o TV para el cliente en Configuración → Cobros.</p>
      )}
    </div>
  )
}

function TransferBox({ status }: { status: CollectStatus }) {
  const t = status.transfer
  const rows = [
    ['Alias', t.alias],
    ['CBU/CVU', t.cbu],
    ['Titular', t.holder],
    ['Banco / billetera', t.bank],
    ['CUIT', t.cuit],
  ].filter(([, v]) => v)
  return (
    <div className="w-full space-y-2 rounded-2xl border p-4" data-testid="transfer-box">
      <p className="flex items-center gap-2 font-medium">
        <Landmark className="size-5" /> Datos para transferir
      </p>
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
        {rows.map(([k, v]) => (
          <div key={k} className="contents">
            <dt className="text-muted-foreground">{k}</dt>
            <dd className="font-mono font-medium break-all">{v}</dd>
          </div>
        ))}
      </dl>
      <p className="text-xs text-muted-foreground">Mirá que la plata haya llegado en tu banco o billetera antes de confirmar.</p>
    </div>
  )
}

function PendingView({ charge, status, method }: { charge: Charge; status: CollectStatus; method: CollectMethod }) {
  const left = useCountdown(charge.expires_at)
  return (
    <div className="flex flex-col items-center gap-3 text-center">
      {charge.kind === 'qr' && charge.qr_png && (
        <img src={charge.qr_png} alt="QR para pagar" className="size-56 rounded-2xl border bg-white p-2" data-testid="pos-charge-qr" />
      )}
      {charge.kind === 'point' && (
        <div className="flex size-40 items-center justify-center rounded-3xl bg-primary/10">
          <Smartphone className="size-20 text-primary" />
        </div>
      )}
      {charge.kind === 'transfer' && <TransferBox status={status} />}
      <p className="flex items-center gap-2 text-muted-foreground" role="status">
        <Loader2 className="size-4 animate-spin" />
        {method === 'transferencia'
          ? 'Esperando que confirmes la transferencia…'
          : method === 'mp_point'
            ? 'Pasá la tarjeta en el Point…'
            : 'Esperando que el cliente pague con su app…'}
      </p>
      {left && <p className="tabular text-sm text-muted-foreground">Vence en {left}</p>}
      {charge.kind === 'qr' && (
        <p className="max-w-sm text-xs text-muted-foreground">
          Se paga desde Mercado Pago o cualquier billetera/app de banco compatible (MODO, Naranja X, Ualá, Santander…).
        </p>
      )}
    </div>
  )
}

function ChargeFlow({
  sale,
  method,
  total,
  onApproved,
  onClose,
}: {
  sale: SaleIn
  method: CollectMethod
  total: number
  onApproved: (sale: SaleDetail) => void
  onClose: () => void
}) {
  const status = useCollectStatus()
  const [chosen, setScreen] = useState<number | null | undefined>(undefined)
  const screen = chosen === undefined ? rememberedScreen(status.data) : chosen
  const create = useCreatePosCharge()
  const [chargeId, setChargeId] = useState<number | null>(null)
  const charge = useCharge(chargeId)
  const action = useChargeAction()
  const ch = charge.data ?? create.data ?? null
  const done = useRef(false)

  useEffect(() => {
    if (ch?.status === 'approved' && ch.sale && !done.current) {
      done.current = true
      onApproved(ch.sale)
    }
  }, [ch, onApproved])

  const start = () => {
    remember(screen)
    create.mutate({ sale, method, screen_id: screen }, { onSuccess: (c) => setChargeId(c.id) })
  }

  if (!status.data) return <Loader2 className="mx-auto my-10 size-8 animate-spin text-primary" />

  if (!ch) {
    const Icon = method === 'transferencia' ? Landmark : method === 'mp_point' ? Smartphone : QrCode
    return (
      <div className="space-y-5">
        <div className="rounded-2xl bg-primary/10 p-4 text-center">
          <p className="text-sm text-muted-foreground">Total a cobrar</p>
          <p className="tabular font-heading text-5xl font-semibold tracking-tight">{fmtMoney(total)}</p>
        </div>
        {method !== 'mp_point' && <ScreenPicker status={status.data} value={screen} onChange={setScreen} />}
        {create.error && <p className="text-sm text-destructive">{create.error.message}</p>}
        <div className="grid grid-cols-2 gap-2">
          <Button variant="outline" className="h-14 text-base" onClick={onClose}>
            Volver
          </Button>
          <Button className="h-14 text-base" onClick={start} disabled={create.isPending} autoFocus>
            {create.isPending ? <Loader2 className="animate-spin" /> : <Icon />}
            {method === 'transferencia' ? 'Mostrar datos' : method === 'mp_point' ? 'Enviar al Point' : 'Generar QR'}
          </Button>
        </div>
      </div>
    )
  }

  if (ch.status === 'approved') {
    return (
      <div className="motion-fade flex flex-col items-center gap-4 py-4 text-center" role="status">
        <div className="motion-pop flex size-20 items-center justify-center rounded-full bg-success/15 text-success">
          <CircleCheckBig className="size-11" />
        </div>
        <p className="font-heading text-2xl font-semibold">¡Pago aprobado!</p>
        {ch.error ? (
          <>
            <p className="text-sm text-destructive">La plata entró, pero la venta no se pudo registrar: {ch.error}</p>
            <Button className="h-12" onClick={() => action.mutate({ id: ch.id, action: 'retry' })} disabled={action.isPending}>
              <RotateCw /> Reintentar registrar la venta
            </Button>
          </>
        ) : (
          <Loader2 className="size-6 animate-spin text-muted-foreground" />
        )}
      </div>
    )
  }

  if (ch.status !== 'pending') {
    const msg = { cancelled: 'Cobro cancelado.', expired: 'El cobro venció sin pagarse.', rejected: 'El pago fue rechazado.', refunded: 'Cobro devuelto.' }[ch.status]
    return (
      <div className="flex flex-col items-center gap-4 py-4 text-center">
        <CircleX className="size-14 text-destructive" />
        <p className="text-lg font-medium">{msg}</p>
        <div className="grid w-full grid-cols-2 gap-2">
          <Button variant="outline" className="h-12" onClick={onClose}>
            Volver al cobro
          </Button>
          <Button
            className="h-12"
            onClick={() => {
              setChargeId(null)
              create.reset()
            }}
          >
            <RotateCw /> Intentar de nuevo
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="grid gap-5 md:grid-cols-[1.2fr_1fr]">
      <PendingView charge={ch} status={status.data} method={method} />
      <div className="flex flex-col gap-3">
        <div className="rounded-2xl bg-primary/10 p-4 text-center">
          <p className="text-sm text-muted-foreground">Total</p>
          <p className="tabular font-heading text-4xl font-semibold">{fmtMoney(ch.amount_cents)}</p>
        </div>
        {screen != null && (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <TabletSmartphone className="size-4" /> También se ve en «{status.data.screens.find((s) => s.id === screen)?.name}»
          </p>
        )}
        {ch.kind === 'transfer' && (
          <Button className="h-14 text-base" onClick={() => action.mutate({ id: ch.id, action: 'confirm' })} disabled={action.isPending}>
            <CircleCheckBig /> Pago recibido
          </Button>
        )}
        {ch.provider === 'fake' && (
          <Button
            variant="secondary"
            className="h-12"
            onClick={() => action.mutate({ id: ch.id, action: 'simulate', body: { status: 'approved' } })}
            disabled={action.isPending}
          >
            Simular pago (prueba)
          </Button>
        )}
        <Button
          variant="outline"
          className="mt-auto h-12"
          onClick={() => action.mutate({ id: ch.id, action: 'cancel' })}
          disabled={action.isPending}
        >
          Cancelar cobro
        </Button>
      </div>
    </div>
  )
}

/** POS: charge through QR / Point / transfer; the sale is registered when the payment is approved. */
export function CollectChargeDialog({
  request,
  total,
  onApproved,
  onClose,
}: {
  request: { sale: SaleIn; method: CollectMethod } | null
  total: number
  onApproved: (sale: SaleDetail) => void
  onClose: () => void
}) {
  return (
    <Dialog open={request != null} onOpenChange={(o) => !o && onClose()}>
      <DialogContent
        className="max-h-[95svh] overflow-y-auto sm:max-w-3xl"
        showCloseButton={false}
        onInteractOutside={(e) => e.preventDefault()}
        onEscapeKeyDown={(e) => e.preventDefault()}
      >
        {request && (
          <>
            <DialogHeader>
              <DialogTitle className="font-heading text-2xl">{TITLES[request.method]}</DialogTitle>
              <DialogDescription>La venta se registra sola cuando el pago se aprueba.</DialogDescription>
            </DialogHeader>
            <ChargeFlow sale={request.sale} method={request.method} total={total} onApproved={onApproved} onClose={onClose} />
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}
