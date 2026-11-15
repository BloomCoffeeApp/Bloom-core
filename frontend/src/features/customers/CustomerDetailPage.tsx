import {
  ArrowLeft,
  Cake,
  CalendarClock,
  ChevronLeft,
  ChevronRight,
  Coffee,
  CreditCard,
  Mail,
  MapPin,
  MessageSquareQuote,
  Pencil,
  Phone,
  Receipt,
  Repeat,
  Star,
  Trophy,
  UserX,
  Wallet,
} from 'lucide-react'
import { Suspense, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'

import { hasBirthYear } from './birthday-utils'
import { ConfirmDialog } from '@/components/confirm-dialog'
import { EmptyState } from '@/components/empty-state'
import { StatCard } from '@/components/stat-card'
import { LockBadge } from '@/components/lock-badge'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Skeleton } from '@/components/ui/skeleton'
import { useAuth } from '@/lib/auth'
import { fmtDate, fmtDateTime, fmtMoney, fmtNumber, fmtRelative, PAYMENT_LABEL } from '@/lib/format'
import { cn } from '@/lib/utils'
import { useHasFeature } from '@/features/license/api'
import { LockedNotice } from '@/components/lock-badge'
import { proModules } from '@pro'

import { useCustomer, useCustomerSales, useDeactivateCustomer, useSaveCustomer } from './api'
import { CustomerAvatar, CustomerFormDialog, PaymentDialog, PointsDialog } from './components'
import type { CustomerDetail } from './types'

const MOVEMENT_LABEL: Record<string, string> = { charge: 'Consumo a cuenta', payment: 'Pago', void: 'Anulación' }

function age(birthday: string) {
  const [y, m, d] = birthday.split('-').map(Number)
  const now = new Date()
  let a = now.getFullYear() - y
  if (now.getMonth() + 1 < m || (now.getMonth() + 1 === m && now.getDate() < d)) a--
  return a
}

function isBirthdayToday(birthday: string | null) {
  if (!birthday) return false
  const [, m, d] = birthday.split('-').map(Number)
  const now = new Date()
  return now.getMonth() + 1 === m && now.getDate() === d
}

export function CustomerDetailPage() {
  const { id: idParam } = useParams()
  const id = Number(idParam)
  const { data: c, isLoading, error } = useCustomer(id)

  if (isLoading) return <DetailSkeleton />
  if (error || !c)
    return (
      <EmptyState
        icon={UserX}
        title="No encontramos este cliente"
        description={error?.message}
        action={
          <Button asChild variant="outline">
            <Link to="/clientes">Volver a clientes</Link>
          </Button>
        }
      />
    )
  return <Detail c={c} />
}

function DetailSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-28 w-full rounded-2xl" />
      <div className="grid gap-4 md:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-24 rounded-2xl" />
        ))}
      </div>
      <Skeleton className="h-72 w-full rounded-2xl" />
    </div>
  )
}

function Detail({ c }: { c: CustomerDetail }) {
  const { can } = useAuth()
  const navigate = useNavigate()
  const [editOpen, setEditOpen] = useState(false)
  const [payOpen, setPayOpen] = useState(false)
  const [pointsOpen, setPointsOpen] = useState(false)
  const [confirmOff, setConfirmOff] = useState(false)
  const deactivate = useDeactivateCustomer()
  const save = useSaveCustomer()
  const stampsPro = useHasFeature('loyalty_pro')
  const m = c.metrics
  const bdayToday = isBirthdayToday(c.birthday)

  return (
    <div className="space-y-6">
      <Button variant="ghost" size="sm" asChild className="-ml-2 text-muted-foreground">
        <Link to="/clientes">
          <ArrowLeft /> Clientes
        </Link>
      </Button>

      {/* Header */}
      <Card className="overflow-hidden rounded-2xl py-0">
        <CardContent className="flex flex-col gap-5 p-6 md:flex-row md:items-center">
          <CustomerAvatar id={c.id} name={c.name} className="size-16 text-xl" />
          <div className="min-w-0 flex-1 space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="font-heading text-3xl font-semibold tracking-tight">{c.name}</h1>
              {!c.active && <Badge variant="outline">Inactivo</Badge>}
              {c.locked && <LockBadge />}
              {bdayToday && (
                <Badge className="bg-destructive/10 text-destructive">
                  <Cake /> ¡Hoy cumple años!
                </Badge>
              )}
              {m.visits_30d >= 4 && (
                <Badge variant="outline" className="border-success/40 text-success">
                  Frecuente
                </Badge>
              )}
            </div>
            <div className="flex flex-wrap gap-x-5 gap-y-1 text-sm text-muted-foreground">
              {c.phone && (
                <a href={`tel:${c.phone}`} className="inline-flex items-center gap-1.5 hover:text-foreground">
                  <Phone className="size-4" /> {c.phone}
                </a>
              )}
              {c.email && (
                <a href={`mailto:${c.email}`} className="inline-flex items-center gap-1.5 hover:text-foreground">
                  <Mail className="size-4" /> {c.email}
                </a>
              )}
              {c.address && (
                <span className="inline-flex items-center gap-1.5">
                  <MapPin className="size-4" /> {c.address}
                  {c.address_ref ? ` · ${c.address_ref}` : ''}
                </span>
              )}
              {c.birthday && (
                <span className="inline-flex items-center gap-1.5">
                  <Cake className="size-4" /> {hasBirthYear(c.birthday) ? `${fmtDate(c.birthday)} · ${age(c.birthday)} años` : fmtDate(c.birthday).slice(0, 5)}
                </span>
              )}
              <span className="inline-flex items-center gap-1.5">
                <CalendarClock className="size-4" /> Cliente desde {fmtDate(c.created_at)}
              </span>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => setEditOpen(true)}>
              <Pencil /> Editar
            </Button>
            {can('customers.manage') &&
              (c.active ? (
                <Button variant="ghost" className="text-destructive" onClick={() => setConfirmOff(true)}>
                  <UserX /> Desactivar
                </Button>
              ) : (
                <Button variant="ghost" onClick={() => save.mutate({ id: c.id, data: { active: true } })}>
                  Reactivar
                </Button>
              ))}
          </div>
        </CardContent>
        {c.notes && (
          <div className="flex items-start gap-3 border-t bg-warning/10 px-6 py-4">
            <MessageSquareQuote className="mt-0.5 size-5 shrink-0 text-warning-foreground dark:text-warning" />
            <div>
              <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">Preferencias</p>
              <p className="text-base font-medium whitespace-pre-line">{c.notes}</p>
            </div>
          </div>
        )}
      </Card>

      {c.locked && <LockedNotice what="Este cliente" />}

      {/* Metrics */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Total gastado" value={fmtMoney(m.total_spent_cents, { short: true })} icon={Wallet} hint={`${m.tickets} tickets`} />
        <StatCard label="Ticket promedio" value={fmtMoney(m.avg_ticket_cents, { short: true })} icon={Receipt} />
        <StatCard
          label="Última visita"
          value={m.last_visit_at ? (m.days_since_last_visit === 0 ? 'Hoy' : `Hace ${m.days_since_last_visit} d`) : 'Nunca'}
          icon={CalendarClock}
          tone={m.days_since_last_visit != null && m.days_since_last_visit > 30 ? 'warning' : 'default'}
          hint={m.last_visit_at ? fmtDateTime(m.last_visit_at) : undefined}
        />
        <StatCard
          label="Frecuencia"
          value={`${fmtNumber(m.visits_per_month, 1)} / mes`}
          icon={Repeat}
          tone="success"
          hint={`${m.visits_30d} visitas en 30 días`}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          {stampsPro && proModules.CustomerStampCards && (
            <Suspense fallback={null}>
              <proModules.CustomerStampCards customerId={c.id} />
            </Suspense>
          )}
          <SalesHistory customerId={c.id} />
        </div>
        <div className="space-y-6">
          <FavoriteCard c={c} />
          <AccountCard c={c} onPay={() => setPayOpen(true)} />
          <PointsCard c={c} onAdjust={can('customers.manage') ? () => setPointsOpen(true) : undefined} />
        </div>
      </div>

      <CustomerFormDialog open={editOpen} onOpenChange={setEditOpen} customer={c} />
      <PaymentDialog open={payOpen} onOpenChange={setPayOpen} customer={c} />
      <PointsDialog open={pointsOpen} onOpenChange={setPointsOpen} customer={c} />
      <ConfirmDialog
        open={confirmOff}
        onOpenChange={setConfirmOff}
        title={`¿Desactivar a ${c.name}?`}
        description="No va a aparecer en búsquedas ni en el POS. Su historial se conserva y podés reactivarlo cuando quieras."
        confirmLabel="Desactivar"
        destructive
        onConfirm={() => deactivate.mutate(c.id, { onSuccess: () => navigate('/clientes') })}
      />
    </div>
  )
}

function FavoriteCard({ c }: { c: CustomerDetail }) {
  const top = c.metrics.top_products
  const max = top[0]?.qty ?? 1
  return (
    <Card className="rounded-2xl">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Trophy className="size-4 text-primary" /> Lo que más pide
        </CardTitle>
      </CardHeader>
      <CardContent>
        {top.length === 0 ? (
          <p className="text-sm text-muted-foreground">Todavía no tiene compras registradas.</p>
        ) : (
          <div className="space-y-4">
            <div className="flex items-center gap-3 rounded-xl bg-primary/10 p-3">
              <div className="flex size-10 items-center justify-center rounded-lg bg-primary text-primary-foreground">
                <Coffee className="size-5" />
              </div>
              <div className="min-w-0">
                <p className="truncate font-semibold">{top[0].name}</p>
                <p className="text-xs text-muted-foreground">{fmtNumber(top[0].qty, 1)} unidades en total</p>
              </div>
            </div>
            <ul className="space-y-2.5">
              {top.slice(1).map((p) => (
                <li key={p.name} className="space-y-1">
                  <div className="flex justify-between text-sm">
                    <span className="truncate">{p.name}</span>
                    <span className="tabular text-muted-foreground">{fmtNumber(p.qty, 1)}</span>
                  </div>
                  <Progress value={(p.qty / max) * 100} className="h-1.5" />
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function AccountCard({ c, onPay }: { c: CustomerDetail; onPay: () => void }) {
  const used = c.credit_limit_cents > 0 ? Math.min((c.balance_cents / c.credit_limit_cents) * 100, 100) : 0
  return (
    <Card className="rounded-2xl">
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="flex items-center gap-2">
          <CreditCard className="size-4 text-primary" /> Cuenta corriente
        </CardTitle>
        <Button size="sm" onClick={onPay} disabled={c.balance_cents <= 0}>
          Registrar pago
        </Button>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <p className="text-sm text-muted-foreground">Saldo adeudado</p>
          <p
            className={cn(
              'tabular text-3xl font-semibold tracking-tight',
              c.over_limit ? 'text-destructive' : c.balance_cents > 0 ? 'text-foreground' : 'text-success',
            )}
          >
            {fmtMoney(c.balance_cents)}
          </p>
          {c.credit_limit_cents > 0 ? (
            <div className="mt-2 space-y-1">
              <Progress value={used} className={cn('h-2', c.over_limit && '[&>*]:bg-destructive')} />
              <p className="text-xs text-muted-foreground">
                Límite {fmtMoney(c.credit_limit_cents)}
                {c.over_limit && <span className="font-medium text-destructive"> · superado</span>}
              </p>
            </div>
          ) : (
            <p className="mt-1 text-xs text-muted-foreground">
              Sin límite asignado{c.over_limit && <span className="font-medium text-destructive"> · tiene deuda</span>}
            </p>
          )}
        </div>
        {c.account_movements.length === 0 ? (
          <p className="text-sm text-muted-foreground">Sin movimientos.</p>
        ) : (
          <ul className="max-h-72 divide-y overflow-y-auto">
            {c.account_movements.map((mv) => (
              <li key={mv.id} className="flex items-center justify-between gap-3 py-2 text-sm">
                <div className="min-w-0">
                  <p className="font-medium">
                    {MOVEMENT_LABEL[mv.type] ?? mv.type}
                    {mv.method && <span className="font-normal text-muted-foreground"> · {PAYMENT_LABEL[mv.method] ?? mv.method}</span>}
                  </p>
                  <p className="text-xs text-muted-foreground">{fmtDateTime(mv.ts)}</p>
                </div>
                <span className={cn('tabular font-medium', mv.amount_cents < 0 ? 'text-success' : 'text-foreground')}>
                  {mv.amount_cents < 0 ? '−' : '+'}
                  {fmtMoney(Math.abs(mv.amount_cents))}
                </span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}

function PointsCard({ c, onAdjust }: { c: CustomerDetail; onAdjust?: () => void }) {
  return (
    <Card className="rounded-2xl">
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="flex items-center gap-2">
          <Star className="size-4 text-primary" /> Puntos
        </CardTitle>
        {onAdjust && (
          <Button size="sm" variant="outline" onClick={onAdjust}>
            Ajustar
          </Button>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="tabular text-3xl font-semibold tracking-tight">
          {fmtNumber(c.points, 0)} <span className="text-base font-normal text-muted-foreground">pts</span>
        </p>
        {c.loyalty_transactions.length === 0 ? (
          <p className="text-sm text-muted-foreground">Todavía no sumó puntos.</p>
        ) : (
          <ul className="max-h-64 divide-y overflow-y-auto">
            {c.loyalty_transactions.map((t) => (
              <li key={t.id} className="flex items-center justify-between gap-3 py-2 text-sm">
                <div className="min-w-0">
                  <p className="truncate">{t.reason}</p>
                  <p className="text-xs text-muted-foreground">{fmtRelative(t.ts)}</p>
                </div>
                <span className={cn('tabular font-medium', t.points >= 0 ? 'text-success' : 'text-destructive')}>
                  {t.points > 0 ? '+' : ''}
                  {t.points}
                </span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}

function SalesHistory({ customerId }: { customerId: number }) {
  const [page, setPage] = useState(1)
  const { data, isLoading } = useCustomerSales(customerId, page)
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1
  return (
    <Card className="rounded-2xl">
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="flex items-center gap-2">
          <Receipt className="size-4 text-primary" /> Historial de compras
        </CardTitle>
        {data && <span className="text-sm text-muted-foreground">{data.total} tickets</span>}
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        ) : !data?.items.length ? (
          <EmptyState icon={Receipt} title="Sin compras todavía" description="Cuando lo asocies a una venta en el POS, va a aparecer acá." />
        ) : (
          <>
            <ul className="divide-y">
              {data.items.map((s) => (
                <li key={s.id} className="flex items-center gap-4 py-3">
                  <div className="flex size-10 shrink-0 flex-col items-center justify-center rounded-lg bg-muted text-xs leading-tight">
                    <span className="font-semibold">{fmtDate(s.ts).slice(0, 5)}</span>
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">{s.items_summary || 'Venta sin ítems'}</p>
                    <p className="text-xs text-muted-foreground">
                      #{s.number} · {fmtDateTime(s.ts)}
                      {s.payment_methods.length > 0 && ` · ${s.payment_methods.map((p) => PAYMENT_LABEL[p] ?? p).join(' + ')}`}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className={cn('tabular font-semibold', s.status === 'voided' && 'text-muted-foreground line-through')}>
                      {fmtMoney(s.total_cents)}
                    </p>
                    {s.status === 'voided' && <Badge variant="destructive">Anulada</Badge>}
                  </div>
                </li>
              ))}
            </ul>
            {pages > 1 && (
              <div className="mt-3 flex items-center justify-end gap-2 text-sm text-muted-foreground">
                <span>
                  Página {page} de {pages}
                </span>
                <Button variant="outline" size="icon" onClick={() => setPage((p) => p - 1)} disabled={page <= 1}>
                  <ChevronLeft />
                </Button>
                <Button variant="outline" size="icon" onClick={() => setPage((p) => p + 1)} disabled={page >= pages}>
                  <ChevronRight />
                </Button>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  )
}
