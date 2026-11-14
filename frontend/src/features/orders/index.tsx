import { BellRing, ClipboardList, Expand, Globe, MessageCircle, Minimize, MonitorPlay, Receipt, Smartphone, Volume2 } from 'lucide-react'
import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Route, Routes } from 'react-router'
import { toast } from 'sonner'

import { ConfirmDialog } from '@/components/confirm-dialog'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'
import { proModules } from '@pro'
import { useNow } from '@/hooks/use-now'
import { useAuth } from '@/lib/auth'
import { fmtMoney } from '@/lib/format'
import { cn } from '@/lib/utils'

import { useHasFeature } from '../license/api'
import { TeamAccessDialog } from '../team/team-access-dialog'
import { useBoard, useOnlineOrderAction, useResolveCall, useSetOrderStatus, whatsappLink } from './api'
import { OrderCard } from './order-card'
import { printKitchenTicket } from './print'
import { audioReady, loadPrefs, notify, playAlert, savePrefs, type SoundPrefs, unlockAudio } from './sound'
import { SoundMenu } from './sound-menu'
import { fmtClock, liveElapsed, liveLevel } from './timing'
import type { BoardColumn, Level, Order, OrderAction, WaiterCall } from './types'

const STATION_KEY = 'bloom.orders.station'

function loadStation(): number | null {
  try {
    const v = Number(localStorage.getItem(STATION_KEY))
    return Number.isFinite(v) && v > 0 ? v : null
  } catch {
    return null
  }
}

interface Row {
  order: Order
  elapsed: number
  level: Level
}

// Columns come from each state's `column` (backend order_flows): every channel shares the same board.
const COLUMNS: { column: BoardColumn; title: string; empty: string }[] = [
  { column: 'queue', title: 'Nuevos', empty: 'Sin pedidos nuevos' },
  { column: 'preparing', title: 'En preparación', empty: 'Nada en preparación' },
  { column: 'ready', title: 'Listos para entregar', empty: 'Nada para entregar' },
]
const ETA_CHOICES = [10, 15, 20, 30, 45, 60]

/** Opens WhatsApp (Desktop if installed, else Web) with the message already written. */
async function openWhatsApp(o: Order, kind: 'accepted' | 'ready' | 'dispatched' | 'generic') {
  try {
    const { url } = await whatsappLink(o.id, kind)
    window.open(url, '_blank', 'noopener')
  } catch (e) {
    toast.error((e as Error).message)
  }
}

const waKind = (o: Order) =>
  o.status === 'awaiting_pay' || o.status === 'accepted' ? 'accepted' : o.status === 'ready' ? 'ready' : o.status === 'dispatched' ? 'dispatched' : 'generic'

const describe = (o: Order) => `${o.table_label || ''}${o.table_label ? ' · ' : ''}${o.items.reduce((a, i) => a + i.qty, 0)} productos`
const callText = (c: WaiterCall) =>
  c.kind === 'bill' ? `Mesa ${c.table_label} pide la cuenta` : c.kind === 'invoice' ? `Mesa ${c.table_label} pide factura` : `Mesa ${c.table_label} llama al mozo`

function OrdersPage() {
  const [station, setStationState] = useState<number | null>(loadStation)
  const [prefs, setPrefsState] = useState<SoundPrefs>(loadPrefs)
  const [audioOk, setAudioOk] = useState(audioReady)
  const [asking, setAsking] = useState<{ order: Order; action: OrderAction } | null>(null)
  const [reason, setReason] = useState('')
  const [eta, setEta] = useState(20)
  const [waNotify, setWaNotify] = useState(true)
  const [fullscreen, setFullscreen] = useState(false)
  const [teamQr, setTeamQr] = useState(false)
  const { can } = useAuth()
  const rootRef = useRef<HTMLDivElement>(null)

  const proFeature = useHasFeature('orders_pro')
  const board = useBoard(station)
  const data = board.data
  const pro = !!data?.pro && proFeature !== false
  const stations = useMemo(() => (pro ? (data?.stations ?? []) : []), [pro, data?.stations])
  const current = stations.find((s) => s.id === station) ?? null
  const now = useNow(1000).getTime()
  const setStatus = useSetOrderStatus()
  const online = useOnlineOrderAction()
  const resolveCall = useResolveCall()

  const setPrefs = (p: SoundPrefs) => {
    setPrefsState(p)
    savePrefs(p)
  }
  const setStation = (id: number | null) => {
    setStationState(id)
    try {
      if (id) localStorage.setItem(STATION_KEY, String(id))
      else localStorage.removeItem(STATION_KEY)
    } catch {
      /* ignore */
    }
  }

  // A station that no longer exists (or no Pro) falls back to "all".
  const effectiveStation = current ? current.id : null
  if (data && station !== null && effectiveStation === null) setStationState(null) // adjust during render

  const rows: Row[] = useMemo(() => {
    if (!data) return []
    return data.orders.map((o) => {
      const elapsed = liveElapsed(o, board.dataUpdatedAt, now)
      return { order: o, elapsed, level: liveLevel(o, elapsed, data.settings.warn_pct) }
    })
  }, [data, board.dataUpdatedAt, now])

  // ------------------------------------------------------------ alerts
  const seen = useRef<Set<number> | null>(null)
  const seenCalls = useRef<Set<number>>(new Set())
  const printed = useRef<Set<number>>(new Set())
  const fallbackPrinted = useRef<Set<number>>(new Set())
  const lateAlerted = useRef<Set<number>>(new Set())
  const prefsRef = useRef(prefs)
  useEffect(() => {
    prefsRef.current = prefs
  }, [prefs])

  useEffect(() => {
    if (!data) return
    const p = prefsRef.current
    if (seen.current === null) {
      // First load: whatever is already on screen doesn't ring.
      seen.current = new Set(data.orders.map((o) => o.id))
      seenCalls.current = new Set(data.calls.map((c) => c.id))
      printed.current = new Set(data.orders.map((o) => o.id))
      for (const f of data.print_failures ?? []) fallbackPrinted.current.add(f.order_id)
      for (const o of data.orders) if (o.late) lateAlerted.current.add(o.id)
      return
    }
    const fresh = data.orders.filter((o) => !seen.current!.has(o.id))
    fresh.forEach((o) => seen.current!.add(o.id))
    if (fresh.length) {
      const first = fresh[0]
      playAlert('new', p, first.channel, data.pro)
      notify(
        first.online
          ? `Nuevo pedido online #${first.number} · ${first.online.customer_name ?? ''}`
          : first.status === 'pending' ? `Pedido de ${first.table_label ?? 'una mesa'} para confirmar` : `Nuevo pedido #${first.number}`,
        fresh.length > 1 ? `${fresh.length} pedidos nuevos` : describe(first),
        p,
        `order-${first.id}`,
      )
    }
    const calls = data.calls.filter((c) => !seenCalls.current.has(c.id))
    calls.forEach((c) => seenCalls.current.add(c.id))
    if (calls.length) {
      playAlert('call', p)
      notify(callText(calls[0]), 'Desde el menú de la mesa', p, `call-${calls[0].id}`)
    }
    // Pro: the station's screen prints a kitchen ticket for each order that reaches it.
    const st = data.pro ? data.stations.find((s) => s.id === effectiveStation) : undefined
    // With a thermal printer assigned (Configuración → Impresoras) the backend prints it instead,
    // and this screen only prints the ones the printer couldn't (fallback with the print dialog).
    for (const o of data.orders) {
      if (printed.current.has(o.id) || o.received_at == null) continue
      printed.current.add(o.id)
      if (st?.print_tickets && !st.direct_print && o.station_id === st.id) printKitchenTicket(o, st.name)
    }
    for (const f of st ? (data.print_failures ?? []) : []) {
      if (fallbackPrinted.current.has(f.order_id)) continue
      fallbackPrinted.current.add(f.order_id)
      const o = data.orders.find((x) => x.id === f.order_id)
      if (!o || o.station_id !== st!.id) continue
      toast.error(`No se pudo imprimir la comanda #${o.number}: ${f.error}. Se abrió el diálogo de impresión.`, { duration: 8000 })
      printKitchenTicket(o, st!.name)
    }
  }, [data, effectiveStation])

  useEffect(() => {
    for (const r of rows) {
      if (r.level !== 'late' || lateAlerted.current.has(r.order.id)) continue
      if (r.order.column !== 'queue' && r.order.column !== 'preparing') continue
      lateAlerted.current.add(r.order.id)
      playAlert('late', prefsRef.current)
      notify(`Pedido #${r.order.number} atrasado`, `${fmtClock(r.elapsed)} (objetivo ${r.order.target_minutes} min)`, prefsRef.current, `late-${r.order.id}`)
    }
  }, [rows])

  // Switching station: the other station's orders are "already seen".
  useEffect(() => {
    seen.current = null
  }, [effectiveStation])

  // ------------------------------------------------------------ fullscreen
  useEffect(() => {
    const on = () => setFullscreen(document.fullscreenElement === rootRef.current)
    document.addEventListener('fullscreenchange', on)
    return () => document.removeEventListener('fullscreenchange', on)
  }, [])
  const toggleFullscreen = useCallback(async () => {
    try {
      if (document.fullscreenElement) await document.exitFullscreen()
      else await rootRef.current?.requestFullscreen()
    } catch {
      /* not allowed (iframe/webview): ignore */
    }
  }, [])

  const act = {
    busy: setStatus.isPending || online.isPending,
    onAction: (o: Order, a: OrderAction) => {
      if (a.needs) {
        setReason('')
        setEta(o.online?.eta_minutes ?? 20)
        setWaNotify(true)
        setAsking({ order: o, action: a })
      } else setStatus.mutate({ id: o.id, status: a.to })
    },
    onWhatsApp: (o: Order) => void openWhatsApp(o, waKind(o)),
    onOnline: (o: Order, action: 'check-payment' | 'register-sale' | 'update-customer') => online.mutate({ id: o.id, action }),
  }
  const confirmAsk = () => {
    if (!asking) return
    const { order: o, action: a } = asking
    if (a.needs === 'reason' && !reason.trim()) return
    setStatus.mutate(
      { id: o.id, status: a.to, reason: reason.trim() || undefined, eta_minutes: a.needs === 'eta' ? eta : undefined },
      { onSuccess: (row) => a.needs === 'eta' && waNotify && row.online?.customer_phone && void openWhatsApp(row, 'accepted') },
    )
    setAsking(null)
  }

  const pending = rows.filter((r) => r.order.column === 'confirm')
  const payment = rows.filter((r) => r.order.column === 'payment')
  const fresh = pending.filter((r) => r.order.online)
  const inProgress = rows.filter((r) => r.order.column === 'queue' || r.order.column === 'preparing')
  const late = inProgress.filter((r) => r.level === 'late').length

  return (
    <div ref={rootRef} className={cn('flex min-h-full flex-col gap-4 bg-background', fullscreen && 'overflow-y-auto p-4 md:p-6')}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-heading text-3xl font-semibold tracking-tight">Pedidos{current ? ` · ${current.name}` : ''}</h1>
          <p className="mt-1 flex flex-wrap gap-2 text-sm text-muted-foreground" aria-live="polite">
            <span>{inProgress.length} en curso</span>
            {late > 0 && <span className="rounded-full bg-destructive px-2 font-medium text-white">{late} atrasado{late > 1 ? 's' : ''}</span>}
            {pending.length > 0 && <span className="rounded-full bg-info px-2 font-medium text-info-foreground">{pending.length} por confirmar</span>}
            {payment.length > 0 && <span className="rounded-full bg-warning/30 px-2 font-medium">{payment.length} esperando pago</span>}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {stations.length > 0 && (
            <Select value={effectiveStation ? String(effectiveStation) : 'all'} onValueChange={(v) => setStation(v === 'all' ? null : Number(v))}>
              <SelectTrigger className="h-11 min-w-40" aria-label="Estación">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todas las estaciones</SelectItem>
                {stations.map((s) => (
                  <SelectItem key={s.id} value={String(s.id)}>
                    {s.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
          {pro && (
            <Button variant="outline" className="h-11" asChild>
              <a href="/menu/retiro" target="_blank" rel="noreferrer">
                <MonitorPlay /> <span className="hidden lg:inline">Pantalla de retiro</span>
              </a>
            </Button>
          )}
          {proModules.TeamApp && can('orders.manage', 'pos.sell') && (
            <Button variant="outline" className="h-11" onClick={() => setTeamQr(true)}>
              <Smartphone /> <span className="hidden lg:inline">QR para el equipo</span>
            </Button>
          )}
          <SoundMenu prefs={prefs} onChange={setPrefs} pro={pro} />
          <Button variant="outline" className="size-11" onClick={toggleFullscreen} aria-label={fullscreen ? 'Salir de pantalla completa' : 'Pantalla completa'}>
            {fullscreen ? <Minimize /> : <Expand />}
          </Button>
        </div>
      </div>

      {!audioOk && !prefs.muted && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-primary/30 bg-primary/5 p-3">
          <p className="text-sm">Para escuchar los pedidos nuevos en este equipo, activá el sonido (una sola vez).</p>
          <Button
            className="h-11"
            onClick={async () => {
              const ok = await unlockAudio()
              setAudioOk(ok)
              if (ok) playAlert('new', prefs)
            }}
          >
            <Volume2 /> Activar sonido
          </Button>
        </div>
      )}

      {fresh.length > 0 && (
        <section aria-label="Pedidos online nuevos" className="flex flex-col gap-2" data-testid="online-banner">
          {fresh.map(({ order: o }) => (
            <div key={o.id} role="alert" className="flex flex-wrap items-center gap-3 rounded-2xl border-2 border-primary bg-primary/10 py-2 pr-2 pl-3">
              <Globe className="size-5 animate-pulse text-primary" />
              <span className="font-medium">
                Nuevo pedido online #{o.number} · {o.online!.customer_name} · {o.channel === 'delivery' ? 'Delivery' : 'Retira'} ·{' '}
                {fmtMoney(o.online!.total_cents)}
              </span>
              <span className="ml-auto flex gap-2">
                {o.actions.map((a) => (
                  <Button key={a.to} variant={a.tone === 'outline' ? 'outline' : 'default'} className="h-11" onClick={() => act.onAction(o, a)}>
                    {a.label}
                  </Button>
                ))}
              </span>
            </div>
          ))}
        </section>
      )}

      {data && data.calls.length > 0 && (
        <section aria-label="Llamados de mesas" className="flex flex-wrap gap-2">
          {data.calls.map((c) => (
            <div key={c.id} className="flex items-center gap-3 rounded-2xl border-2 border-info bg-info/10 py-1.5 pr-1.5 pl-3" role="alert">
              {c.kind === 'bill' ? <Receipt className="size-5 text-info" /> : <BellRing className="size-5 animate-pulse text-info" />}
              <span className="font-medium">{callText(c)}</span>
              <span className="text-sm text-muted-foreground tabular-nums">{fmtClock(c.elapsed_s + Math.floor((now - board.dataUpdatedAt) / 1000))}</span>
              <Button variant="secondary" className="h-11" disabled={resolveCall.isPending} onClick={() => resolveCall.mutate(c.id)}>
                Atendido
              </Button>
            </div>
          ))}
        </section>
      )}

      {proModules.TableSessionsPanel && (
        <Suspense fallback={null}>
          <proModules.TableSessionsPanel />
        </Suspense>
      )}

      {board.isLoading ? (
        <div className="grid gap-4 md:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-64 rounded-2xl" />
          ))}
        </div>
      ) : board.isError && !data ? (
        <p className="py-16 text-center text-muted-foreground">No se pudo cargar la pantalla de pedidos. Reintentando…</p>
      ) : (
        <>
          {pending.length > 0 && (
            <section aria-label="Por confirmar" className="space-y-2">
              <h2 className="font-heading text-xl font-semibold">Por confirmar</h2>
              <div className="grid grid-cols-[repeat(auto-fill,minmax(min(100%,18rem),1fr))] gap-3">
                {pending.map((r) => (
                  <OrderCard key={r.order.id} order={r.order} elapsed={r.elapsed} level={r.level} actions={act} />
                ))}
              </div>
            </section>
          )}
          {payment.length > 0 && (
            <section aria-label="Esperando pago" className="space-y-2">
              <h2 className="font-heading text-xl font-semibold">Esperando pago</h2>
              <div className="grid grid-cols-[repeat(auto-fill,minmax(min(100%,18rem),1fr))] gap-3">
                {payment.map((r) => (
                  <OrderCard key={r.order.id} order={r.order} elapsed={r.elapsed} level={r.level} actions={act} />
                ))}
              </div>
            </section>
          )}
          {rows.length === 0 ? (
            <div className="flex flex-1 flex-col items-center justify-center gap-3 py-20 text-center text-muted-foreground">
              <ClipboardList className="size-12 text-primary/60" />
              <p className="font-heading text-xl text-foreground">No hay pedidos en curso</p>
              <p className="max-w-sm text-sm">Las ventas del punto de venta, los pedidos de las mesas y los pedidos online aparecen acá al instante.</p>
            </div>
          ) : (
            <div className="grid flex-1 grid-cols-[repeat(auto-fit,minmax(min(100%,18rem),1fr))] items-start gap-4">
              {COLUMNS.map((col) => {
                const items = rows.filter((r) => r.order.column === col.column)
                return (
                  <section key={col.column} aria-label={col.title} className="flex min-w-0 flex-col gap-3 rounded-2xl bg-muted/40 p-2.5">
                    <h2 className="flex items-center justify-between px-1 font-heading text-lg font-semibold">
                      {col.title}
                      <span className="rounded-full bg-card px-2.5 text-base tabular-nums">{items.length}</span>
                    </h2>
                    {items.length === 0 ? (
                      <p className="px-1 py-6 text-center text-sm text-muted-foreground">{col.empty}</p>
                    ) : (
                      items.map((r) => <OrderCard key={r.order.id} order={r.order} elapsed={r.elapsed} level={r.level} actions={act} />)
                    )}
                  </section>
                )
              })}
            </div>
          )}
        </>
      )}

      <ConfirmDialog
        open={asking != null}
        onOpenChange={(o) => !o && setAsking(null)}
        title={
          asking?.action.needs === 'eta'
            ? `Aceptar el pedido #${asking.order.number}`
            : `¿${asking?.action.label} el pedido #${asking?.order.number}?`
        }
        description={
          asking?.action.needs === 'eta'
            ? asking.order.online?.payment_method === 'cash'
              ? 'Se cobra al entregar. Pasa directo a preparación.'
              : 'Al aceptar se habilita el pago para el cliente; se prepara cuando esté pagado.'
            : asking?.action.needs === 'reason'
              ? 'El cliente ve el motivo en la página de su pedido.'
              : asking?.order.payment_status === 'paid' && asking.order.online?.payment_method === 'online'
                ? 'Se devuelve el pago completo por el mismo medio.'
                : asking?.order.status === 'pending'
                  ? 'No llega a la barra y no se cobra. El cliente ve el pedido como cancelado.'
                  : 'Sale de la pantalla. Si ya se cobró en la caja, anulá la venta desde Ventas.'
        }
        confirmLabel={asking?.action.needs === 'eta' ? 'Aceptar' : (asking?.action.label ?? 'Confirmar')}
        destructive={asking?.action.tone === 'danger' || asking?.action.to === 'rejected' || asking?.action.to === 'cancelled'}
        onConfirm={confirmAsk}
      >
        {asking?.action.needs === 'eta' ? (
          <div className="space-y-3">
            <p className="text-sm font-medium">Tiempo estimado</p>
            <div className="flex flex-wrap gap-2" role="group" aria-label="Tiempo estimado">
              {ETA_CHOICES.map((m) => (
                <Button key={m} type="button" variant={eta === m ? 'default' : 'outline'} className="h-11 min-w-16" onClick={() => setEta(m)}>
                  {m} min
                </Button>
              ))}
              <Input
                type="number"
                min={1}
                max={600}
                value={eta}
                onChange={(e) => setEta(Math.max(1, Math.min(600, Number(e.target.value) || 1)))}
                className="h-11 w-24"
                aria-label="Minutos"
              />
            </div>
            {asking.order.online?.customer_phone && (
              <label className="flex min-h-11 items-center gap-2 text-sm">
                <Checkbox checked={waNotify} onCheckedChange={(v) => setWaNotify(v === true)} />
                <MessageCircle className="size-4" /> Avisar por WhatsApp (con el link para seguirlo y pagar)
              </label>
            )}
          </div>
        ) : asking?.action.needs === 'confirm' ? null : (
          <Textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder={asking?.action.needs === 'reason' ? 'Motivo (el cliente lo ve)' : 'Motivo (opcional)'}
            maxLength={200}
            rows={2}
            aria-label="Motivo"
          />
        )}
      </ConfirmDialog>
      {proModules.TeamApp && <TeamAccessDialog open={teamQr} onOpenChange={setTeamQr} />}
    </div>
  )
}

export default function Module() {
  return (
    <Routes>
      <Route path="*" element={<OrdersPage />} />
    </Routes>
  )
}
