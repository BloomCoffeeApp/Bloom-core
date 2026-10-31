import { ArrowLeft, PartyPopper, ShoppingCart, Truck } from 'lucide-react'
import { Link, useNavigate } from 'react-router'

import { EmptyState } from '@/components/empty-state'
import { PageHeader } from '@/components/page-header'
import { Button } from '@/components/ui/button'
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useAuth } from '@/lib/auth'
import { fmtMoney, fmtNumber, fmtQty } from '@/lib/format'

import { useHasFeature } from '@/features/license/api'

import { useCreateOrderFromSuggestions } from './purchasing'
import { useSuggestions } from './api'
import { StatusBadge } from './components'

export function SuggestionsPage() {
  const { data, isLoading } = useSuggestions()
  const { can } = useAuth()
  const createOrder = useCreateOrderFromSuggestions()
  const purchasesPro = useHasFeature('purchases')
  const navigate = useNavigate()
  const total = data?.reduce((a, g) => a + g.total_est_cents, 0) ?? 0

  return (
    <div>
      <PageHeader
        title="Sugerencias de compra"
        description="Insumos bajo mínimo, con el consumo promedio de los últimos 14 días para cubrir una semana."
        actions={
          <Button variant="outline" asChild>
            <Link to="/stock">
              <ArrowLeft /> Volver a stock
            </Link>
          </Button>
        }
      />
      {isLoading ? (
        <div className="grid gap-4">
          {Array.from({ length: 2 }).map((_, i) => (
            <Skeleton key={i} className="h-56 rounded-2xl" />
          ))}
        </div>
      ) : !data?.length ? (
        <EmptyState
          icon={PartyPopper}
          title="¡Todo en orden!"
          description="No hay insumos bajo el mínimo. Volvé a mirar después de un par de días de ventas."
        />
      ) : (
        <div className="space-y-6">
          <p className="text-sm text-muted-foreground">
            {data.reduce((a, g) => a + g.items.length, 0)} insumos para reponer · costo estimado{' '}
            <span className="tabular font-medium text-foreground">{fmtMoney(total)}</span>
          </p>
          {data.map((g) => (
            <Card key={g.supplier_id ?? 'none'} className="rounded-2xl">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-lg">
                  <Truck className="size-5 text-primary" /> {g.supplier_name}
                </CardTitle>
                <CardDescription>
                  {g.items.length} {g.items.length === 1 ? 'insumo' : 'insumos'} · estimado{' '}
                  <span className="tabular">{fmtMoney(g.total_est_cents)}</span>
                </CardDescription>
                {can('encargado') && purchasesPro && (
                  <CardAction>
                    <Button
                      disabled={!g.supplier_id || createOrder.isPending}
                      title={g.supplier_id ? undefined : 'Asigná un proveedor habitual a estos insumos'}
                      onClick={() =>
                        g.supplier_id &&
                        createOrder.mutate(g.supplier_id, {
                          onSuccess: (o) => navigate(`/compras?tab=ordenes&orden=${o.id}`),
                        })
                      }
                    >
                      <ShoppingCart /> Crear orden de compra
                    </Button>
                  </CardAction>
                )}
              </CardHeader>
              <CardContent>
                <div className="overflow-hidden rounded-xl border">
                  <Table>
                    <TableHeader>
                      <TableRow className="hover:bg-transparent">
                        <TableHead>Insumo</TableHead>
                        <TableHead>Estado</TableHead>
                        <TableHead className="text-right">Actual</TableHead>
                        <TableHead className="text-right">Mínimo</TableHead>
                        <TableHead className="text-right">Consumo/día</TableHead>
                        <TableHead className="text-right">Sugerido</TableHead>
                        <TableHead className="text-right">Estimado</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {g.items.map((i) => (
                        <TableRow key={i.stock_item_id}>
                          <TableCell className="font-medium">{i.name}</TableCell>
                          <TableCell>
                            <StatusBadge status={i.status} />
                          </TableCell>
                          <TableCell className="tabular text-right">{fmtQty(i.current_qty, i.unit)}</TableCell>
                          <TableCell className="tabular text-right text-muted-foreground">{fmtQty(i.min_qty, i.unit)}</TableCell>
                          <TableCell className="tabular text-right text-muted-foreground">
                            {i.daily_consumption ? `${fmtNumber(i.daily_consumption, 1)} ${i.unit}` : '—'}
                          </TableCell>
                          <TableCell className="tabular text-right font-semibold text-primary">
                            {fmtQty(i.suggested_qty, i.unit)}
                          </TableCell>
                          <TableCell className="tabular text-right">{fmtMoney(i.est_cost_cents)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
