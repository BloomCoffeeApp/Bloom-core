import { Printer } from 'lucide-react'
import type { ReactNode } from 'react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Skeleton } from '@/components/ui/skeleton'
import { fmtDateTime, fmtMoney, fmtNumber } from '@/lib/format'

import { useCashSession } from './api'
import { DiffText } from './dialogs'
import { printZReport } from './z-report'

function Row({ label, value, strong }: { label: string; value: ReactNode; strong?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-3 py-1 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className={strong ? 'tabular text-base font-semibold' : 'tabular'}>{value}</span>
    </div>
  )
}

export function ZDetailSheet({ id, onOpenChange }: { id: number | null; onOpenChange: (o: boolean) => void }) {
  const { data: s, isLoading } = useCashSession(id)
  return (
    <Sheet open={id != null} onOpenChange={onOpenChange}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
        <SheetHeader>
          <SheetTitle className="font-heading text-xl">Cierre de caja #{id}</SheetTitle>
          <SheetDescription>
            {s ? `${fmtDateTime(s.opened_at)} → ${s.closed_at ? fmtDateTime(s.closed_at) : 'abierta'}` : ' '}
          </SheetDescription>
        </SheetHeader>
        {isLoading || !s ? (
          <div className="space-y-3 px-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-8 w-full" />
            ))}
          </div>
        ) : (
          <div className="space-y-5 px-4 pb-6">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={s.status === 'open' ? 'default' : 'secondary'}>
                {s.status === 'open' ? 'Abierta' : 'Cerrada'}
              </Badge>
              <span className="text-sm text-muted-foreground">
                Abrió {s.opened_by_name ?? '—'}
                {s.closed_by_name ? ` · cerró ${s.closed_by_name}` : ''}
              </span>
              <Button className="ml-auto" variant="outline" onClick={() => printZReport(s)}>
                <Printer /> Imprimir Z
              </Button>
            </div>

            <div className="rounded-2xl border p-4">
              <Row label="Fondo inicial" value={fmtMoney(s.opening_cents)} />
              <Row label="Tickets" value={s.tickets} />
              <Row label="Ticket promedio" value={fmtMoney(s.avg_ticket_cents)} />
              <Row label="Descuentos" value={fmtMoney(s.discounts_cents)} />
              <Row label={`Anulaciones (${s.voided_count})`} value={fmtMoney(s.voided_total_cents)} />
              <Row label="Ingresos / egresos" value={`${fmtMoney(s.movements_in_cents)} / −${fmtMoney(s.movements_out_cents)}`} />
              <Separator className="my-2" />
              <Row label="Ventas" value={fmtMoney(s.sales_total_cents)} strong />
            </div>

            <div>
              <h3 className="mb-2 font-medium">Arqueo por medio de pago</h3>
              <div className="overflow-hidden rounded-2xl border text-sm">
                <div className="grid grid-cols-4 gap-2 bg-muted/50 px-3 py-2 text-xs text-muted-foreground">
                  <span>Medio</span>
                  <span className="text-right">Esperado</span>
                  <span className="text-right">Contado</span>
                  <span className="text-right">Dif.</span>
                </div>
                {s.by_method.map((m) => (
                  <div key={m.method} className="grid grid-cols-4 gap-2 border-t px-3 py-2">
                    <span className="truncate">{m.name}</span>
                    <span className="tabular text-right">{fmtMoney(m.expected_cents)}</span>
                    <span className="tabular text-right">{m.counted_cents == null ? '—' : fmtMoney(m.counted_cents)}</span>
                    <DiffText cents={m.difference_cents} className="text-right" />
                  </div>
                ))}
                <div className="flex justify-between border-t bg-muted/30 px-3 py-2 font-medium">
                  <span>Diferencia total</span>
                  <DiffText cents={s.difference_cents} />
                </div>
              </div>
            </div>

            <div>
              <h3 className="mb-2 font-medium">Ventas por categoría</h3>
              <div className="space-y-1.5">
                {s.by_category.length === 0 && <p className="text-sm text-muted-foreground">Sin ventas.</p>}
                {s.by_category.map((c) => {
                  const pct = s.sales_total_cents ? (c.total_cents / s.sales_total_cents) * 100 : 0
                  return (
                    <div key={c.name} className="space-y-1">
                      <div className="flex justify-between text-sm">
                        <span>
                          {c.name} <span className="text-muted-foreground">· {fmtNumber(c.qty, 0)} u.</span>
                        </span>
                        <span className="tabular">{fmtMoney(c.total_cents)}</span>
                      </div>
                      <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                        <div className="h-full rounded-full bg-primary" style={{ width: `${pct}%` }} />
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>

            {s.movements.length > 0 && (
              <div>
                <h3 className="mb-2 font-medium">Movimientos</h3>
                <div className="space-y-1 text-sm">
                  {s.movements.map((m) => (
                    <div key={m.id} className="flex justify-between gap-3">
                      <span className="truncate text-muted-foreground">{m.reason}</span>
                      <span className={m.type === 'in' ? 'tabular text-success' : 'tabular text-destructive'}>
                        {m.type === 'in' ? '+' : '−'}
                        {fmtMoney(m.amount_cents)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {s.notes && (
              <p className="rounded-xl bg-muted/50 p-3 text-sm">
                <span className="font-medium">Observaciones: </span>
                {s.notes}
              </p>
            )}
          </div>
        )}
      </SheetContent>
    </Sheet>
  )
}
