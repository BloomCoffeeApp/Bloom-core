import { Undo2 } from 'lucide-react'
import { useState } from 'react'

import { MoneyInput } from '@/components/money-input'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { useAuth } from '@/lib/auth'
import { fmtDateTime, fmtMoney } from '@/lib/format'

import type { SaleDetail } from '../sales/types'
import { useRefundSale, useSaleCharge } from './api'

const MP_METHODS = ['mp_qr', 'mp_point']

/** Sale detail: refunds through Mercado Pago (full or partial) for sales collected with QR / Point. */
export function SaleRefundPanel({ sale }: { sale: SaleDetail }) {
  const { can } = useAuth()
  const viaMp = sale.payments.some((p) => MP_METHODS.includes(p.method))
  const info = useSaleCharge(sale.id, viaMp)
  const [open, setOpen] = useState(false)
  if (!viaMp || !info.data?.charge) return null
  const { charge, refunds, refundable_cents } = info.data
  return (
    <div className="space-y-2 rounded-xl border p-3 text-sm" data-testid="sale-refund-panel">
      <div className="flex items-center justify-between gap-2">
        <span className="text-muted-foreground">Cobrado con Mercado Pago</span>
        {charge.refunded_cents > 0 && <span className="font-medium text-destructive">Devuelto {fmtMoney(charge.refunded_cents)}</span>}
      </div>
      {refunds.map((r) => (
        <p key={r.id} className="text-xs text-muted-foreground">
          {fmtDateTime(r.ts)} · {fmtMoney(r.amount_cents)}
          {r.reason ? ` · ${r.reason}` : ''}
        </p>
      ))}
      {refundable_cents > 0 && can('sales.void') && (
        <Button variant="outline" className="h-11 w-full" onClick={() => setOpen(true)}>
          <Undo2 /> Devolver
        </Button>
      )}
      {open && (
        <RefundDialog
          saleId={sale.id}
          refundable={refundable_cents}
          canVoid={sale.status === 'completed' && charge.refunded_cents === 0}
          onClose={() => setOpen(false)}
        />
      )}
    </div>
  )
}

function RefundDialog({ saleId, refundable, canVoid, onClose }: { saleId: number; refundable: number; canVoid: boolean; onClose: () => void }) {
  const refund = useRefundSale(saleId)
  const [amount, setAmount] = useState<number | null>(refundable)
  const [reason, setReason] = useState('')
  const [voidSale, setVoidSale] = useState(canVoid)
  const full = amount === refundable
  const valid = amount != null && amount > 0 && amount <= refundable
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Devolver por Mercado Pago</DialogTitle>
          <DialogDescription>La plata vuelve a la cuenta o tarjeta con la que pagó el cliente.</DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="refund-amount">Monto a devolver</Label>
            <MoneyInput value={amount} onChange={setAmount} aria-label="Monto a devolver" className="[&_input]:h-11" />
            <p className="text-xs text-muted-foreground">Podés devolver hasta {fmtMoney(refundable)}.</p>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="refund-reason">Motivo (opcional)</Label>
            <Input id="refund-reason" value={reason} maxLength={200} onChange={(e) => setReason(e.target.value)} className="h-11" />
          </div>
          {canVoid && full && (
            <label className="flex items-center justify-between gap-3 rounded-xl border p-3">
              <span className="text-sm">
                <span className="font-medium">Anular también la venta</span>
                <span className="block text-xs text-muted-foreground">Devuelve el stock y la saca de la caja.</span>
              </span>
              <Switch checked={voidSale} onCheckedChange={setVoidSale} aria-label="Anular también la venta" />
            </label>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" className="h-11" onClick={onClose}>
            Cancelar
          </Button>
          <Button
            variant="destructive"
            className="h-11"
            disabled={!valid || refund.isPending}
            onClick={() =>
              refund.mutate(
                { amount_cents: full ? null : amount, reason: reason.trim() || null, void_sale: canVoid && full && voidSale },
                { onSuccess: onClose },
              )
            }
          >
            <Undo2 /> {refund.isPending ? 'Devolviendo…' : `Devolver ${amount ? fmtMoney(amount) : ''}`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
