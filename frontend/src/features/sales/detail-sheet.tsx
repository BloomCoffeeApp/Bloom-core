import { Ban, Printer, User } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { ConfirmDialog } from '@/components/confirm-dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
import { Sheet, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'
import { useAuth } from '@/lib/auth'
import { fmtDateTime, fmtMoney, fmtNumber, PAYMENT_LABEL } from '@/lib/format'

import { usePaymentMethods, useSale, useVoidSale } from './api'
import { SaleRefundPanel } from '../collect/refund-panel'
import { CourtesyBadge } from './courtesy-badge'
import { printTicket } from './print'
import { CHANNEL_LABEL } from './types'

export function SaleDetailSheet({ id, onOpenChange }: { id: number | null; onOpenChange: (o: boolean) => void }) {
  const { data: s, isLoading } = useSale(id)
  const { data: methods } = usePaymentMethods()
  const { can } = useAuth()
  const voidM = useVoidSale()
  const [confirm, setConfirm] = useState(false)
  const [reason, setReason] = useState('')
  const methodName = (code: string) => methods?.find((m) => m.code === code)?.name ?? PAYMENT_LABEL[code] ?? code
  const manualDisc = s ? s.discount_cents - s.points_discount_cents : 0

  const doVoid = () => {
    if (!s) return
    if (reason.trim().length < 3) {
      toast.error('Indicá el motivo de la anulación')
      return
    }
    voidM.mutate(
      { id: s.id, reason: reason.trim() },
      {
        onSuccess: (done) => {
          done.warnings?.forEach((w) => toast.warning(w))
          const tab = s.table_tab ? ` La cuenta de la ${s.table_tab.table_label ?? 'mesa'} se reabrió.` : ''
          toast.success(`Ticket #${s.number} anulado. Se reintegró el stock.${tab}`)
          setReason('')
          setConfirm(false)
        },
        onError: (e) => toast.error(e.message),
      },
    )
  }

  return (
    <Sheet open={id != null} onOpenChange={onOpenChange}>
      <SheetContent className="w-full sm:max-w-lg">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2 font-heading text-xl">
            Ticket #{s?.number ?? '…'}
            {s?.is_courtesy && <CourtesyBadge />}
            {s?.status === 'voided' && <Badge variant="destructive">Anulado</Badge>}
          </SheetTitle>
          <SheetDescription>
            {s ? `${fmtDateTime(s.ts)} · ${CHANNEL_LABEL[s.channel]}${s.table_label ? ` · Mesa ${s.table_label}` : ''}${s.waiter_name ? ` · Mozo: ${s.waiter_name}` : ''} · ${s.user_name ?? '—'}` : ' '}
          </SheetDescription>
        </SheetHeader>
        <div className="flex-1 overflow-y-auto px-4">
          {isLoading || !s ? (
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : (
            <div className="space-y-5 pb-4">
              {s.status === 'voided' && (
                <div className="rounded-xl bg-destructive/10 p-3 text-sm text-destructive">
                  Anulado por {s.voided_by_name ?? '—'} {s.voided_at ? `el ${fmtDateTime(s.voided_at)}` : ''}. Motivo: {s.void_reason}
                </div>
              )}
              {s.is_courtesy && (
                <div className="rounded-xl bg-primary/10 p-3 text-sm" data-testid="courtesy-note">
                  <p className="font-medium">Cortesía · invita la casa</p>
                  <p className="text-muted-foreground">
                    {fmtMoney(s.courtesy_cents)} a precio de carta, sin cobrar.
                    {s.courtesy_reason ? ` Para / motivo: ${s.courtesy_reason}` : ''}
                  </p>
                </div>
              )}
              {s.customer && (
                <div className="flex items-center gap-3 rounded-xl border p-3">
                  <div className="flex size-9 items-center justify-center rounded-full bg-primary/10 text-primary">
                    <User className="size-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium">{s.customer.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {s.points_earned ? `+${s.points_earned} pts` : 'Sin puntos'}
                      {s.points_redeemed ? ` · canjeó ${s.points_redeemed} pts` : ''}
                    </p>
                  </div>
                </div>
              )}
              <div className="space-y-3">
                {s.items.map((it) => (
                  <div key={it.id} className="flex gap-3">
                    <span className="tabular w-8 shrink-0 text-muted-foreground">{fmtNumber(it.qty)}×</span>
                    <div className="min-w-0 flex-1">
                      <p className="font-medium">
                        <span>{it.name_snapshot}</span>
                        {it.size_name && <span className="ml-1.5 text-sm font-normal text-muted-foreground">{it.size_name}</span>}
                      </p>
                      {it.modifiers?.length ? (
                        <p className="text-xs text-muted-foreground">{it.modifiers.map((m) => m.name).join(' · ')}</p>
                      ) : null}
                      {it.notes && <p className="text-xs text-muted-foreground italic">“{it.notes}”</p>}
                      {it.discount_cents > 0 && !s.is_courtesy && (
                        <p className="text-xs text-success">Desc. −{fmtMoney(it.discount_cents)}</p>
                      )}
                      {s.is_courtesy && (
                        <p className="tabular text-xs text-muted-foreground line-through">{fmtMoney(it.unit_price_cents * it.qty)}</p>
                      )}
                    </div>
                    <span className="tabular">{fmtMoney(it.total_cents)}</span>
                  </div>
                ))}
              </div>
              <Separator />
              <div className="space-y-1 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Subtotal</span>
                  <span className="tabular">{fmtMoney(s.subtotal_cents)}</span>
                </div>
                {manualDisc > 0 && (
                  <div className="flex justify-between text-success">
                    <span>Descuento</span>
                    <span className="tabular">−{fmtMoney(manualDisc)}</span>
                  </div>
                )}
                {s.points_discount_cents > 0 && (
                  <div className="flex justify-between text-success">
                    <span>Canje de puntos</span>
                    <span className="tabular">−{fmtMoney(s.points_discount_cents)}</span>
                  </div>
                )}
                {s.delivery_fee_cents > 0 && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Envío</span>
                    <span className="tabular">{fmtMoney(s.delivery_fee_cents)}</span>
                  </div>
                )}
                <div className="flex justify-between pt-1 text-lg font-semibold">
                  <span>Total</span>
                  <span className="tabular">{fmtMoney(s.total_cents)}</span>
                </div>
                {s.tip_cents > 0 && (
                  <div className="flex justify-between" data-testid="sale-tip">
                    <span className="text-muted-foreground">Propina</span>
                    <span className="tabular">{fmtMoney(s.tip_cents)}</span>
                  </div>
                )}
                {can('reports.view') && (
                  <div className="flex justify-between text-xs text-muted-foreground">
                    <span>Costo estimado</span>
                    <span className="tabular">
                      {fmtMoney(s.cost_cents)}
                      {s.total_cents > 0 && ` · margen ${Math.round(((s.total_cents - s.cost_cents) / s.total_cents) * 100)}%`}
                    </span>
                  </div>
                )}
              </div>
              <Separator />
              <div className="space-y-2">
                <p className="text-sm font-medium">Pagos</p>
                {s.payments.map((p) => (
                  <div key={p.id} className="rounded-xl bg-muted/50 px-3 py-2 text-sm">
                    <div className="flex justify-between">
                      <span>{methodName(p.method)}</span>
                      <span className="tabular font-medium">{fmtMoney(p.amount_cents)}</span>
                    </div>
                    {p.tendered_cents != null && (
                      <p className="text-xs text-muted-foreground">
                        Entregó {fmtMoney(p.tendered_cents)} · vuelto {fmtMoney(p.change_cents)}
                      </p>
                    )}
                  </div>
                ))}
                {s.payments.length === 0 && (
                  <p className="text-sm text-muted-foreground">
                    {s.is_courtesy ? 'Sin pagos (cortesía, no se cobra).' : 'Sin pagos (total cubierto con puntos).'}
                  </p>
                )}
              </div>
              <SaleRefundPanel sale={s} />
              {s.notes && <p className="rounded-xl bg-muted/50 p-3 text-sm">{s.notes}</p>}
            </div>
          )}
        </div>
        {s && (
          <SheetFooter className="flex-row gap-2 border-t">
            <Button variant="outline" size="lg" className="flex-1" onClick={() => printTicket(s.id)}>
              <Printer /> Reimprimir
            </Button>
            {s.status === 'completed' && can('sales.void') && (
              <Button variant="destructive" size="lg" className="flex-1" onClick={() => setConfirm(true)}>
                <Ban /> Anular
              </Button>
            )}
          </SheetFooter>
        )}
        <ConfirmDialog
          open={confirm}
          onOpenChange={setConfirm}
          title={`¿Anular el ticket #${s?.number ?? ''}?`}
          description="Se reintegra el stock, se revierten los puntos y la cuenta corriente. La venta queda registrada como anulada."
          confirmLabel="Anular venta"
          destructive
          onConfirm={doVoid}
        >
          {s?.table_tab && (
            <p className="rounded-xl border border-warning/40 bg-warning/10 p-3 text-sm" data-testid="void-reopens-tab">
              La cuenta de la {s.table_tab.table_label ?? 'mesa'} se va a reabrir: vuelve a «Mesas abiertas» para cobrarla de nuevo
              (los pedidos ya entregados no se mandan otra vez a la barra).
            </p>
          )}
          <div className="space-y-2">
            <Label htmlFor="void-reason">Motivo</Label>
            <Textarea
              id="void-reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Ej.: error de carga, el cliente se arrepintió…"
              rows={2}
              autoFocus
            />
          </div>
        </ConfirmDialog>
      </SheetContent>
    </Sheet>
  )
}
