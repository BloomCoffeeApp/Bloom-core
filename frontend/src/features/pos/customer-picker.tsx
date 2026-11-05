import { Search, Star, UserPlus, Users } from 'lucide-react'
import { useEffect, useState } from 'react'
import { toast } from 'sonner'

import { EmptyState } from '@/components/empty-state'
import { LockBadge } from '@/components/lock-badge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { fmtMoney } from '@/lib/format'

import { useCreateCustomer, useCustomerSearch } from './api'
import type { PosCustomer } from './types'

function useDebounced<T>(value: T, ms = 250) {
  const [v, setV] = useState(value)
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms)
    return () => clearTimeout(t)
  }, [value, ms])
  return v
}

export function CustomerPicker({
  open,
  onOpenChange,
  onPick,
}: {
  open: boolean
  onOpenChange: (o: boolean) => void
  onPick: (c: PosCustomer) => void
}) {
  const [q, setQ] = useState('')
  const [creating, setCreating] = useState(false)
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')
  const dq = useDebounced(q.trim())
  const { data, isLoading, error } = useCustomerSearch(dq, open && !creating)
  const create = useCreateCustomer()

  const pick = (c: PosCustomer) => {
    onPick(c)
    onOpenChange(false)
    setQ('')
    setCreating(false)
  }

  const submit = () => {
    if (!name.trim()) return toast.error('Ingresá el nombre')
    create.mutate(
      { name: name.trim(), phone: phone.trim() || null },
      {
        onSuccess: (c) => {
          toast.success(`Cliente ${c.name} creado`)
          setName('')
          setPhone('')
          pick({ ...c, points: c.points ?? 0, balance_cents: c.balance_cents ?? 0, credit_limit_cents: c.credit_limit_cents ?? 0 })
        },
        onError: (e) => toast.error(e.message),
      },
    )
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{creating ? 'Nuevo cliente' : 'Elegir cliente'}</DialogTitle>
          <DialogDescription>
            {creating ? 'Alta rápida: después podés completar sus datos en Clientes.' : 'Buscá por nombre o teléfono para sumar puntos.'}
          </DialogDescription>
        </DialogHeader>
        {creating ? (
          <div className="space-y-3">
            <div className="space-y-2">
              <Label htmlFor="nc-name">Nombre</Label>
              <Input id="nc-name" className="h-12 text-base" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
            </div>
            <div className="space-y-2">
              <Label htmlFor="nc-phone">Teléfono (opcional)</Label>
              <Input
                id="nc-phone"
                className="h-12 text-base"
                inputMode="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && submit()}
              />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" className="h-11" onClick={() => setCreating(false)}>
                Volver
              </Button>
              <Button className="h-11 px-5" onClick={submit} disabled={create.isPending}>
                Crear y asociar
              </Button>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="relative">
              <Search className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                autoFocus
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Nombre o teléfono…"
                className="h-12 pl-9 text-base"
                onKeyDown={(e) => {
                  const first = data?.find((c) => !c.locked)
                  if (e.key === 'Enter' && first) pick(first)
                }}
              />
            </div>
            <div className="max-h-80 space-y-1 overflow-y-auto">
              {isLoading ? (
                Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-14 w-full rounded-xl" />)
              ) : error ? (
                <p className="p-3 text-sm text-destructive">{error.message}</p>
              ) : !data?.length ? (
                <EmptyState icon={Users} title="Sin resultados" description="Podés crearlo en un toque." />
              ) : (
                data.map((c) => (
                  <button
                    key={c.id}
                    disabled={c.locked}
                    title={c.locked ? 'Bloqueado en el plan gratuito: no se puede asociar a una venta.' : undefined}
                    onClick={() => pick(c)}
                    className="flex min-h-14 w-full items-center gap-3 rounded-xl px-3 py-2 text-left hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:bg-transparent"
                  >
                    <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-primary/10 font-semibold text-primary">
                      {c.name.slice(0, 1).toUpperCase()}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="flex items-center gap-2 font-medium">
                        <span className="truncate">{c.name}</span>
                        {c.locked && <LockBadge />}
                      </p>
                      <p className="truncate text-xs text-muted-foreground">{c.phone ?? 'Sin teléfono'}</p>
                    </div>
                    <div className="text-right text-xs">
                      <p className="flex items-center justify-end gap-1 font-medium">
                        <Star className="size-3 text-warning" /> {c.points} pts
                      </p>
                      {c.balance_cents > 0 && <p className="text-destructive">Debe {fmtMoney(c.balance_cents)}</p>}
                    </div>
                  </button>
                ))
              )}
            </div>
            <Button
              variant="outline"
              className="h-12 w-full"
              onClick={() => {
                setCreating(true)
                setName(/\d{4,}/.test(q) ? '' : q)
                setPhone(/\d{4,}/.test(q) ? q : '')
              }}
            >
              <UserPlus /> Crear cliente nuevo
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
