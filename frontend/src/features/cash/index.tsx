import {
  ArrowDownCircle,
  ArrowUpCircle,
  Banknote,
  History,
  Lock,
  Receipt,
  ShoppingCart,
  Unlock,
  Wallet,
} from 'lucide-react'
import { useState } from 'react'
import { Link, Route, Routes } from 'react-router'

import { DataTable, type ColumnDef } from '@/components/data-table'
import { EmptyState } from '@/components/empty-state'
import { PageHeader } from '@/components/page-header'
import { StatCard } from '@/components/stat-card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { fmtDateTime, fmtMoney, fmtRelative, fmtTime } from '@/lib/format'

import { useCashSessions, useCurrentCash } from './api'
import { CloseCashDialog, DiffText, MovementDialog, OpenCashDialog } from './dialogs'
import type { CashSession, CashSessionListItem } from './types'
import { ZDetailSheet } from './z-detail'

function CurrentSession({ s }: { s: CashSession }) {
  const cash = s.by_method.find((m) => m.method === 'efectivo')
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Fondo inicial" value={fmtMoney(s.opening_cents)} icon={Wallet} hint={`Abierta ${fmtRelative(s.opened_at)}`} />
        <StatCard label="Ventas del turno" value={fmtMoney(s.sales_total_cents)} icon={ShoppingCart} tone="success" hint={s.voided_count ? `${s.voided_count} anuladas` : undefined} />
        <StatCard
          label="Efectivo esperado"
          value={fmtMoney(s.expected_cash_cents)}
          icon={Banknote}
          tone="warning"
          hint={`Ventas en efectivo ${fmtMoney(cash?.sales_cents ?? 0)}`}
        />
        <StatCard label="Tickets" value={s.tickets} icon={Receipt} hint={`Promedio ${fmtMoney(s.avg_ticket_cents)}`} />
      </div>

      <div className="grid gap-6 lg:grid-cols-5">
        <Card className="rounded-2xl lg:col-span-2">
          <CardHeader>
            <CardTitle>Por medio de pago</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1">
            {s.by_method.map((m) => (
              <div key={m.method} className="flex items-center justify-between gap-3 rounded-xl px-2 py-2 hover:bg-muted/50">
                <div>
                  <p className="font-medium">{m.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {m.count} ventas · {fmtMoney(m.sales_cents)}
                  </p>
                </div>
                <div className="text-right">
                  <p className="tabular font-semibold">{fmtMoney(m.expected_cents)}</p>
                  <p className="text-xs text-muted-foreground">esperado</p>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card className="rounded-2xl lg:col-span-3">
          <CardHeader>
            <CardTitle>Movimientos de caja</CardTitle>
          </CardHeader>
          <CardContent>
            {s.movements.length === 0 ? (
              <EmptyState icon={Wallet} title="Sin movimientos" description="Los ingresos y egresos de efectivo aparecen acá." />
            ) : (
              <div className="divide-y">
                {s.movements.map((m) => (
                  <div key={m.id} className="flex items-center gap-3 py-2.5">
                    {m.type === 'in' ? (
                      <ArrowDownCircle className="size-5 shrink-0 text-success" />
                    ) : (
                      <ArrowUpCircle className="size-5 shrink-0 text-destructive" />
                    )}
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-medium">{m.reason}</p>
                      <p className="text-xs text-muted-foreground">
                        {fmtTime(m.ts)} · {m.user_name ?? '—'}
                      </p>
                    </div>
                    <span className={m.type === 'in' ? 'tabular font-semibold text-success' : 'tabular font-semibold text-destructive'}>
                      {m.type === 'in' ? '+' : '−'}
                      {fmtMoney(m.amount_cents)}
                    </span>
                  </div>
                ))}
                <div className="flex justify-between pt-3 text-sm text-muted-foreground">
                  <span>Ingresos {fmtMoney(s.movements_in_cents)}</span>
                  <span>Egresos {fmtMoney(s.movements_out_cents)}</span>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

const historyColumns: ColumnDef<CashSessionListItem, unknown>[] = [
  { accessorKey: 'id', header: '#', cell: ({ row }) => <span className="tabular text-muted-foreground">#{row.original.id}</span> },
  { accessorKey: 'opened_at', header: 'Apertura', cell: ({ row }) => fmtDateTime(row.original.opened_at) },
  {
    accessorKey: 'closed_at',
    header: 'Cierre',
    cell: ({ row }) =>
      row.original.status === 'open' ? <Badge>Abierta</Badge> : fmtDateTime(row.original.closed_at),
  },
  { accessorKey: 'opened_by_name', header: 'Responsable', cell: ({ row }) => row.original.closed_by_name ?? row.original.opened_by_name ?? '—' },
  { accessorKey: 'tickets', header: 'Tickets', cell: ({ row }) => <span className="tabular">{row.original.tickets}</span> },
  { accessorKey: 'sales_total_cents', header: 'Ventas', cell: ({ row }) => <span className="tabular font-medium">{fmtMoney(row.original.sales_total_cents)}</span> },
  { accessorKey: 'difference_cents', header: 'Diferencia', cell: ({ row }) => <DiffText cents={row.original.difference_cents} /> },
]

function CashPage() {
  const current = useCurrentCash()
  const sessions = useCashSessions()
  const [openDlg, setOpenDlg] = useState(false)
  const [closeDlg, setCloseDlg] = useState(false)
  const [mvType, setMvType] = useState<'in' | 'out' | null>(null)
  const [zId, setZId] = useState<number | null>(null)
  const s = current.data

  return (
    <>
      <PageHeader
        title="Caja"
        description={s ? `Turno abierto por ${s.opened_by_name ?? '—'} el ${fmtDateTime(s.opened_at)}` : 'Apertura, movimientos y arqueo de caja'}
        actions={
          s ? (
            <>
              <Button variant="outline" size="lg" onClick={() => setMvType('in')}>
                <ArrowDownCircle className="text-success" /> Ingreso
              </Button>
              <Button variant="outline" size="lg" onClick={() => setMvType('out')}>
                <ArrowUpCircle className="text-destructive" /> Egreso
              </Button>
              <Button variant="outline" size="lg" asChild>
                <Link to="/pos">
                  <ShoppingCart /> Ir al POS
                </Link>
              </Button>
              <Button size="lg" onClick={() => setCloseDlg(true)}>
                <Lock /> Cerrar caja
              </Button>
            </>
          ) : (
            !current.isLoading && (
              <Button size="lg" onClick={() => setOpenDlg(true)}>
                <Unlock /> Abrir caja
              </Button>
            )
          )
        }
      />

      <Tabs defaultValue="turno">
        <TabsList className="mb-4">
          <TabsTrigger value="turno">
            <Wallet /> Turno actual
          </TabsTrigger>
          <TabsTrigger value="historial">
            <History /> Historial de cierres
          </TabsTrigger>
        </TabsList>
        <TabsContent value="turno">
          {current.isLoading ? (
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-28 rounded-2xl" />
              ))}
            </div>
          ) : s ? (
            <CurrentSession s={s} />
          ) : (
            <EmptyState
              icon={Lock}
              title="La caja está cerrada"
              description="Abrí la caja con el fondo de cambio para empezar a vender."
              action={
                <Button size="lg" onClick={() => setOpenDlg(true)}>
                  <Unlock /> Abrir caja
                </Button>
              }
            />
          )}
        </TabsContent>
        <TabsContent value="historial">
          <DataTable
            columns={historyColumns}
            data={sessions.data}
            loading={sessions.isLoading}
            searchable={false}
            onRowClick={(r) => setZId(r.id)}
            emptyTitle="Todavía no hay cierres"
          />
        </TabsContent>
      </Tabs>

      <OpenCashDialog open={openDlg} onOpenChange={setOpenDlg} />
      <MovementDialog type={mvType} onOpenChange={(o) => !o && setMvType(null)} />
      {s && <CloseCashDialog session={s} open={closeDlg} onOpenChange={setCloseDlg} onClosed={(z) => setZId(z.id)} />}
      <ZDetailSheet id={zId} onOpenChange={(o) => !o && setZId(null)} />
    </>
  )
}

export default function Module() {
  return (
    <Routes>
      <Route index element={<CashPage />} />
      <Route path="*" element={<CashPage />} />
    </Routes>
  )
}
