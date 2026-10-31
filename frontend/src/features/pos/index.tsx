import { CircleCheckBig, Lock, Printer, Plus, Unlock } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Route, Routes } from 'react-router'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog'
import { fmtMoney } from '@/lib/format'

import { useCurrentCash } from '../cash/api'
import { OpenCashDialog } from '../cash/dialogs'
import { useCreateSale, usePaymentMethods } from '../sales/api'
import { printTicket } from '../sales/print'
import type { PaymentIn, SaleDetail } from '../sales/types'
import { usePosCatalog, usePosConfig } from './api'
import { CartPanel } from './cart-panel'
import { CheckoutDialog } from './checkout-dialog'
import { ModifierDialog } from './modifier-dialog'
import { ProductGrid } from './product-grid'
import type { PosProduct } from './types'
import { computeTotals, useCart } from './use-cart'

function SuccessDialog({ sale, onNew }: { sale: SaleDetail | null; onNew: () => void }) {
  return (
    <Dialog open={sale != null} onOpenChange={(o) => !o && onNew()}>
      <DialogContent className="sm:max-w-md" showCloseButton={false}>
        {sale && (
          <div className="flex flex-col items-center gap-4 py-2 text-center">
            <div className="flex size-20 items-center justify-center rounded-full bg-success/15 text-success">
              <CircleCheckBig className="size-11" />
            </div>
            <div>
              <DialogTitle className="font-heading text-3xl">¡Venta cobrada!</DialogTitle>
              <DialogDescription className="mt-1 text-base">
                Ticket <span className="tabular font-semibold text-foreground">#{sale.number}</span> · {fmtMoney(sale.total_cents)}
              </DialogDescription>
            </div>
            {sale.change_cents > 0 && (
              <div className="w-full rounded-2xl bg-warning/20 p-4">
                <p className="text-sm text-muted-foreground">Vuelto</p>
                <p className="tabular font-heading text-5xl font-semibold">{fmtMoney(sale.change_cents)}</p>
              </div>
            )}
            {sale.points_earned > 0 && sale.customer && (
              <p className="text-sm text-muted-foreground">
                {sale.customer.name} sumó {sale.points_earned} puntos (total {sale.customer.points}).
              </p>
            )}
            <div className="grid w-full grid-cols-2 gap-2">
              <Button variant="outline" className="h-14 text-base" onClick={() => printTicket(sale.id)}>
                <Printer /> Imprimir ticket
              </Button>
              <Button className="h-14 text-base" onClick={onNew} autoFocus>
                <Plus /> Nueva venta
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}

function PosPage() {
  const catalog = usePosCatalog()
  const config = usePosConfig()
  const cash = useCurrentCash()
  const { data: methods } = usePaymentMethods()
  const cartApi = useCart()
  const createSale = useCreateSale()
  const searchRef = useRef<HTMLInputElement>(null)

  const [modProduct, setModProduct] = useState<PosProduct | null>(null)
  const [checkout, setCheckout] = useState(false)
  const [done, setDone] = useState<SaleDetail | null>(null)
  const [openCash, setOpenCash] = useState(false)

  const totals = useMemo(() => computeTotals(cartApi.cart, config.data), [cartApi.cart, config.data])
  const cashOpen = !!cash.data
  const cashKnownClosed = !cash.isLoading && !cash.isError && !cash.data

  const pick = useCallback(
    (p: PosProduct) => {
      if (p.modifier_groups.length > 0) setModProduct(p)
      else cartApi.add(p)
    },
    [cartApi],
  )

  const startCheckout = useCallback(() => {
    if (!cartApi.cart.lines.length) return
    if (!cashOpen) {
      setOpenCash(true)
      return
    }
    setCheckout(true)
  }, [cartApi.cart.lines.length, cashOpen])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'F2') {
        e.preventDefault()
        searchRef.current?.focus()
        searchRef.current?.select()
      } else if (e.key === 'F9') {
        e.preventDefault()
        if (!checkout && !modProduct && !done) startCheckout()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [checkout, modProduct, done, startCheckout])

  const confirm = (payments: PaymentIn[]) => {
    const { cart } = cartApi
    createSale.mutate(
      {
        items: cart.lines.map((l) => ({
          product_id: l.product_id,
          qty: l.qty,
          modifier_ids: l.modifiers.map((m) => m.id),
          notes: l.notes || null,
          discount_cents: l.discount_cents,
        })),
        customer_id: cart.customer?.id ?? null,
        channel: cart.channel,
        table_label: cart.channel === 'salon' ? cart.table_label.trim() || null : null,
        discount_cents: totals.discount,
        points_to_redeem: cart.points_to_redeem,
        payments,
      },
      {
        onSuccess: (sale) => {
          setCheckout(false)
          cartApi.clear()
          setDone(sale)
        },
        onError: (e) => toast.error(e.message),
      },
    )
  }

  return (
    <div className="grid h-[calc(100svh-3.5rem)] grid-cols-[minmax(0,1fr)] grid-rows-[minmax(0,1fr)_minmax(0,50%)] overflow-hidden md:grid-cols-[1fr_340px] md:grid-rows-1 lg:grid-cols-[1fr_400px] xl:grid-cols-[1fr_440px]">
      <ProductGrid
        catalog={catalog.data}
        loading={catalog.isLoading}
        error={catalog.error}
        onPick={pick}
        searchRef={searchRef}
      />
      <div className="relative flex min-h-0 flex-col">
        <CartPanel cartApi={cartApi} totals={totals} config={config.data} cashOpen={cashOpen} onCheckout={startCheckout} />
        {cashKnownClosed && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-background/80 p-6 backdrop-blur-sm">
            <div className="flex flex-col items-center gap-3 rounded-2xl border bg-card p-6 text-center shadow-lg">
              <div className="flex size-14 items-center justify-center rounded-2xl bg-warning/20">
                <Lock className="size-7" />
              </div>
              <div>
                <p className="font-heading text-xl font-semibold">La caja está cerrada</p>
                <p className="mt-1 text-sm text-muted-foreground">Abrila para empezar a cobrar.</p>
              </div>
              <Button className="h-12 px-6 text-base" onClick={() => setOpenCash(true)}>
                <Unlock /> Abrir caja
              </Button>
            </div>
          </div>
        )}
      </div>

      <ModifierDialog
        product={modProduct}
        onOpenChange={(o) => !o && setModProduct(null)}
        onConfirm={(p, mods, qty, notes) => cartApi.add(p, mods, qty, notes)}
      />
      <CheckoutDialog
        open={checkout}
        onOpenChange={setCheckout}
        total={totals.total}
        methods={methods ?? []}
        customer={cartApi.cart.customer}
        submitting={createSale.isPending}
        onConfirm={confirm}
      />
      <SuccessDialog
        sale={done}
        onNew={() => {
          setDone(null)
          setTimeout(() => searchRef.current?.focus(), 50)
        }}
      />
      <OpenCashDialog open={openCash} onOpenChange={setOpenCash} />
    </div>
  )
}

export default function Module() {
  return (
    <Routes>
      <Route index element={<PosPage />} />
      <Route path="*" element={<PosPage />} />
    </Routes>
  )
}
