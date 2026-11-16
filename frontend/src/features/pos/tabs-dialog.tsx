import { ArrowRightLeft, ChefHat, LayoutGrid } from 'lucide-react'

import { EmptyState } from '@/components/empty-state'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { fmtMoney, fmtNumber, fmtTime } from '@/lib/format'

import type { Tab } from '../orders/types'

/** Open tables ("mesas abiertas"): pick one to charge it from the cart. */
export function TabsDialog({
  open,
  onOpenChange,
  tabs,
  onPick,
  onMove,
}: {
  open: boolean
  onOpenChange: (o: boolean) => void
  tabs: Tab[]
  onPick: (tab: Tab) => void
  /** Pro «Cambiar de mesa»: pass the account to another table (the customers moved). */
  onMove?: (tab: Tab) => void
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Mesas abiertas</DialogTitle>
          <DialogDescription>Pedidos confirmados que todavía no se cobraron. Elegí una mesa para cobrarla.</DialogDescription>
        </DialogHeader>
        {tabs.length === 0 ? (
          <EmptyState icon={LayoutGrid} title="No hay mesas abiertas" description="Los pedidos confirmados desde las mesas aparecen acá." />
        ) : (
          <ul className="max-h-[60svh] space-y-2 overflow-y-auto">
            {tabs.map((t) => (
              <li key={t.id} className="rounded-2xl border p-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="font-heading text-xl font-semibold">
                      Mesa {t.table_label}
                      {t.table_code && <span className="ml-2 align-middle font-mono text-xs font-normal text-muted-foreground">{t.table_code}</span>}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Abierta {fmtTime(t.opened_at)} · {t.orders} pedido{t.orders === 1 ? '' : 's'}
                      {t.unfinished > 0 && (
                        <span className="ml-1 inline-flex items-center gap-1 text-warning-foreground dark:text-warning">
                          <ChefHat className="size-3" /> {t.unfinished} en preparación
                        </span>
                      )}
                    </p>
                  </div>
                  <Button className="h-12 px-5 text-base" onClick={() => onPick(t)} aria-label={`Cobrar mesa ${t.table_label}`}>
                    Cobrar <span className="tabular">{fmtMoney(t.total_cents)}</span>
                  </Button>
                </div>
                {onMove && (
                  <Button variant="ghost" size="sm" className="mt-2 -ml-2 text-muted-foreground" onClick={() => onMove(t)} data-testid="tab-move">
                    <ArrowRightLeft /> Cambiar de mesa
                  </Button>
                )}
                <ul className="mt-2 space-y-0.5 text-sm text-muted-foreground">
                  {t.lines.map((ln, i) => (
                    <li key={i}>
                      {fmtNumber(ln.qty, 1)}× {ln.name}
                      {ln.size_name ? ` (${ln.size_name})` : ''}
                      {ln.modifiers.length ? ` · ${ln.modifiers.join(', ')}` : ''}
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        )}
      </DialogContent>
    </Dialog>
  )
}
