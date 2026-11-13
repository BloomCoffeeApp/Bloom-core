import { CircleCheckBig, Gift, Lock, Printer, Plus, Unlock } from 'lucide-react'
import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Route, Routes } from 'react-router'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog'
import { fmtMoney } from '@/lib/format'
import { useModules } from '@/features/business/api'
import { useHasFeature } from '@/features/license/api'
import type { StampReward } from '@/pro-modules'
import { proModules } from '@pro'

import { useCurrentCash } from '../cash/api'
import { OpenCashDialog } from '../cash/dialogs'
import { useCreateSale, usePaymentMethods } from '../sales/api'
import { afterSale } from '../printing/direct'
import { usePrintingStatus } from '../printing/api'
import { printTicket, printTicketDialog } from '../sales/print'
import type { Channel, SaleDetail, SaleIn } from '../sales/types'
import { useCollectStatus } from '../collect/api'
import { CollectChargeDialog } from '../collect/charge-dialog'
import type { CollectMethod } from '../collect/types'
import { useOpenTabs } from '../orders/api'
import { usePosCatalog, usePosConfig, usePosQuote } from './api'
import { TabsDialog } from './tabs-dialog'
import { CartPanel, type PosSections } from './cart-panel'
import { CheckoutDialog, type CheckoutConfirm } from './checkout-dialog'
import { ModifierDialog } from './modifier-dialog'
import { ProductGrid } from './product-grid'
import type { PosProduct } from './types'
import { computeTotals, useCart } from './use-cart'

function SuccessDialog({ sale, onNew }: { sale: SaleDetail | null; onNew: () => void }) {
  // Ticket mode (Configuración → Impresoras): "nunca" doesn't offer the ticket here (reprint from Ventas).
  const offerTicket = usePrintingStatus().data?.ticket_mode !== 'never'
  return (
    <Dialog open={sale != null} onOpenChange={(o) => !o && onNew()}>
      <DialogContent className="sm:max-w-md" showCloseButton={false}>
        {sale && (
          <div className="flex flex-col items-center gap-4 py-2 text-center">
            <div className="flex size-20 items-center justify-center rounded-full bg-success/15 text-success">
              {sale.is_courtesy ? <Gift className="size-11" /> : <CircleCheckBig className="size-11" />}
            </div>
            <div>
              <DialogTitle className="font-heading text-3xl">{sale.is_courtesy ? '¡Cortesía registrada!' : '¡Venta cobrada!'}</DialogTitle>
              <DialogDescription className="mt-1 text-base">
                Ticket <span className="tabular font-semibold text-foreground">#{sale.number}</span> ·{' '}
                {sale.is_courtesy ? `Invita la casa (${fmtMoney(sale.courtesy_cents)} a precio de carta)` : fmtMoney(sale.total_cents)}
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
            <div className={offerTicket ? 'grid w-full grid-cols-2 gap-2' : 'grid w-full gap-2'}>
              {offerTicket && (
                <Button variant="outline" className="h-14 text-base" onClick={() => printTicket(sale.id)}>
                  <Printer /> Imprimir ticket
                </Button>
              )}
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
  const [tabsOpen, setTabsOpen] = useState(false)
  const [tip, setTip] = useState(0) // optional tip of the checkout in progress (QR/Point charge include it)
  const [collectReq, setCollectReq] = useState<{ sale: SaleIn; method: CollectMethod } | null>(null)
  const collect = useCollectStatus()
  const tabs = useOpenTabs()

  // Business type: only the channels/sections this kind of business uses.
  const modules = useModules()
  const sections = useMemo<PosSections>(() => {
    const channels = (
      [['dine_in', 'salon'], ['takeaway', 'llevar'], ['delivery', 'delivery']] as const
    ).flatMap(([m, c]): Channel[] => (modules.on(m) ? [c] : []))
    return { channels, tables: modules.on('tables'), customers: modules.on('customers'), loyalty: modules.on('loyalty') }
  }, [modules])
  const { setChannel } = cartApi
  const channel = cartApi.cart.channel
  const onTab = !!cartApi.cart.tab
  useEffect(() => {
    if (!onTab && sections.channels.length && !sections.channels.includes(channel)) setChannel(sections.channels[0])
  }, [channel, onTab, sections.channels, setChannel])

  // Automatic promotions (Pro): the backend prices the cart; checkout waits for a fresh quote.
  const promosOn = useHasFeature('promos') === true && proModules.edition === 'pro'
  const quote = usePosQuote(promosOn ? cartApi.cart.lines : [])
  const quoteLines = promosOn && cartApi.cart.lines.length ? quote.data?.lines : undefined
  const pricing = promosOn && cartApi.cart.lines.length > 0 && (quote.isFetching || quote.isPlaceholderData)
  const totals = useMemo(
    () => computeTotals(cartApi.cart, config.data, quoteLines),
    [cartApi.cart, config.data, quoteLines],
  )
  // A table the phones already (partly) paid: the cashier collects only what is left.
  const prepaid = Math.min(cartApi.cart.tab?.prepaid_cents ?? 0, totals.total)
  const payTotal = Math.max(totals.total - prepaid, 0)
  const stampsOn = useHasFeature('loyalty_pro') === true && !!proModules.PosStampCards

  const redeem = useCallback(
    (r: StampReward) => {
      if (r.kind === 'product') {
        const p = catalog.data?.products.find((x) => x.id === r.product_id)
        if (!p) return toast.error('El producto del premio no está en el catálogo del POS')
        const size = r.size_id != null ? (p.sizes.find((s) => s.size_id === r.size_id) ?? null) : null
        cartApi.addReward(p, size ?? p.sizes.find((s) => s.is_default) ?? p.sizes[0] ?? null, {
          program_id: r.program_id,
          label: r.label,
        })
      } else {
        cartApi.setReward({ program_id: r.program_id, label: r.label, kind: r.kind, value: r.value })
      }
      toast.success(`Premio agregado: ${r.label}`)
    },
    [catalog.data, cartApi],
  )
  const redeemed = useMemo(
    () => [
      ...cartApi.cart.lines.flatMap((l) => (l.reward ? [l.reward.program_id] : [])),
      ...(cartApi.cart.reward ? [cartApi.cart.reward.program_id] : []),
    ],
    [cartApi.cart],
  )
  const cashOpen = !!cash.data
  const cashKnownClosed = !cash.isLoading && !cash.isError && !cash.data

  const pick = useCallback(
    (p: PosProduct) => {
      if (p.modifier_groups.length > 0 || p.sizes.length > 1) setModProduct(p)
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

  const listTotal = useMemo(() => cartApi.cart.lines.reduce((a, l) => a + l.unit_cents * l.qty, 0), [cartApi.cart.lines])

  const confirm: CheckoutConfirm = (payments, courtesy, tipCents = 0, waiterId = null) => {
    setTip(tipCents)
    const { cart } = cartApi
    const body: SaleIn = {
      items: cart.lines.map((l) => ({
        product_id: l.product_id,
        size_id: l.size?.size_id ?? null,
        qty: l.qty,
        modifier_ids: l.modifiers.map((m) => m.id),
        notes: l.notes || null,
        // A courtesy gives the whole cart away: no discounts, points or payments.
        discount_cents: courtesy ? 0 : l.discount_cents,
        to_bar: l.to_bar !== false,
        reward_program_id: courtesy ? null : (l.reward?.program_id ?? null),
      })),
      customer_id: cart.customer?.id ?? null,
      channel: cart.channel,
      table_label: cart.channel === 'salon' ? cart.table_label.trim() || null : null,
      discount_cents: courtesy ? 0 : totals.discount,
      points_to_redeem: courtesy ? 0 : cart.points_to_redeem,
      payments: courtesy ? [] : payments,
      is_courtesy: !!courtesy,
      courtesy_reason: courtesy?.reason || null,
      tab_id: cart.tab?.id ?? null,
      tip_cents: courtesy ? 0 : tipCents,
      waiter_employee_id: cart.tab ? waiterId : null,
      reward_program_id: courtesy ? null : (cart.reward?.program_id ?? null),
    }
    // QR / Point / transfer shown to the customer (Pro `payments`): the sale is registered on approval.
    const collectPay = courtesy ? undefined : payments.find((p) => collect.data?.methods.includes(p.method as CollectMethod))
    if (collectPay) {
      setCheckout(false)
      setCollectReq({ sale: body, method: collectPay.method as CollectMethod })
      return
    }
    createSale.mutate(body, { onSuccess: onSold, onError: (e) => toast.error(e.message) })
  }

  const onSold = (sale: SaleDetail) => {
    setCheckout(false)
    setCollectReq(null)
    cartApi.clear()
    setDone(sale)
    // Thermal printer: automatic ticket and/or cash drawer (falls back to the print dialog).
    void afterSale(sale, () => printTicketDialog(sale.id))
  }

  return (
    <div className="grid h-[calc(100svh-3.5rem)] grid-cols-[minmax(0,1fr)] grid-rows-[minmax(0,1fr)_minmax(0,50%)] overflow-hidden md:grid-cols-[minmax(0,1fr)_340px] md:grid-rows-1 lg:grid-cols-[minmax(0,1fr)_400px] xl:grid-cols-[minmax(0,1fr)_440px]">
      <ProductGrid
        catalog={catalog.data}
        loading={catalog.isLoading}
        error={catalog.error}
        onPick={pick}
        searchRef={searchRef}
      />
      <div className="relative flex min-h-0 flex-col">
        <CartPanel
          cartApi={cartApi}
          totals={totals}
          config={config.data}
          cashOpen={cashOpen}
          onCheckout={startCheckout}
          openTabs={tabs.data?.length ?? 0}
          onOpenTabs={() => setTabsOpen(true)}
          quote={quoteLines}
          pricing={pricing}
          sections={sections}
          customerExtras={
            stampsOn && cartApi.cart.customer && proModules.PosStampCards ? (
              <Suspense fallback={null}>
                <proModules.PosStampCards customerId={cartApi.cart.customer.id} redeemed={redeemed} onRedeem={redeem} />
              </Suspense>
            ) : null
          }
        />
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
        onConfirm={(p, mods, qty, notes, size) => cartApi.add(p, mods, qty, notes, size)}
      />
      <CheckoutDialog
        open={checkout}
        onOpenChange={setCheckout}
        total={payTotal}
        prepaid={prepaid}
        tips={config.data?.tips}
        tabId={cartApi.cart.tab?.id ?? null}
        listTotal={listTotal}
        methods={methods ?? []}
        customer={cartApi.cart.customer}
        submitting={createSale.isPending}
        onConfirm={confirm}
      />
      <CollectChargeDialog
        request={collectReq}
        total={payTotal + tip}
        onApproved={onSold}
        onClose={() => {
          setCollectReq(null)
          setCheckout(true)
        }}
      />
      <SuccessDialog
        sale={done}
        onNew={() => {
          setDone(null)
          setTimeout(() => searchRef.current?.focus(), 50)
        }}
      />
      <OpenCashDialog open={openCash} onOpenChange={setOpenCash} />
      <TabsDialog
        open={tabsOpen}
        onOpenChange={setTabsOpen}
        tabs={tabs.data ?? []}
        onPick={(tab) => {
          if (tab.paying_cents > 0) toast.warning('Hay un pago en curso desde la mesa: esperá a que termine para cobrarla.')
          const missing = cartApi.loadTab(tab, catalog.data?.products ?? [])
          if (missing.length) toast.warning(`No están en el catálogo: ${missing.join(', ')}`)
          setTabsOpen(false)
        }}
      />
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
