import { Check, ChevronDown, Clock, Lock, Pause, Search, Sparkles } from 'lucide-react'
import { useMemo, useState } from 'react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { fmtDateTime } from '@/lib/format'
import { cn } from '@/lib/utils'

import { type FreeItem, type FreeKind, useChooseFreeActives, useFreeKindItems, useFreePlan } from './api'

const KINDS: { kind: FreeKind; label: string; one: string; many: string }[] = [
  { kind: 'products', label: 'Productos', one: 'producto', many: 'productos' },
  { kind: 'customers', label: 'Clientes', one: 'cliente', many: 'clientes' },
  { kind: 'stock_items', label: 'Insumos', one: 'insumo', many: 'insumos' },
  { kind: 'users', label: 'Usuarios', one: 'usuario', many: 'usuarios' },
]

/** Configuración → "Elegí tus activos": which items stay usable on the free plan. */
export function FreeActivesSection() {
  const plan = useFreePlan()
  const [kind, setKind] = useState<FreeKind>('products')
  const [open, setOpen] = useState(false)

  if (!plan.data) return <Skeleton className="h-96 rounded-2xl" />
  const o = plan.data
  return (
    <div className="space-y-4" data-testid="free-actives">
      <Card className="rounded-2xl">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 font-heading text-lg">
            {o.limited ? <Lock className="size-5 text-warning" /> : <Sparkles className="size-5 text-primary" />}
            {o.limited ? 'Elegí tus activos' : 'Si algún día volvés al plan gratuito'}
          </CardTitle>
          <CardDescription>
            {o.limited ? (
              <>
                En el plan gratuito solo una parte de lo que cargaste queda <b>activo para usar</b>. Lo demás no se borra
                ni se esconde: queda con candado, conserva su historial y a los clientes se les puede seguir cobrando la
                cuenta corriente.
              </>
            ) : (
              <>
                Con Pro <b>todo está activo y no hay nada bloqueado</b>. Esto es solo por si algún día pasás al plan
                gratuito: elegí qué quedaría activo (por defecto, lo más antiguo); lo demás quedaría en pausa, sin
                borrarse.
              </>
            )}
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-2 text-sm text-muted-foreground sm:grid-cols-2">
          {!o.limited && (
            <div className="sm:col-span-2">
              <Button variant="outline" className="h-11 gap-2" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
                {open ? 'Ocultar la selección' : 'Elegir qué quedaría activo'}
                <ChevronDown className={cn('size-4 transition-transform', open && 'rotate-180')} />
              </Button>
            </div>
          )}
          {o.limited && (
            <>
            <p className="flex items-start gap-2">
              <Check className="mt-0.5 size-4 shrink-0 text-success" />
              Sumar uno en un lugar libre (por ejemplo, después de archivar otro) se puede cuando quieras.
            </p>
            <p className="flex items-start gap-2">
              <Clock className="mt-0.5 size-4 shrink-0 text-warning" />
              Cambiar un activo por uno bloqueado se puede una vez cada {o.cooldown_days}{' '}
              {o.cooldown_days === 1 ? 'día' : 'días'}.
            </p>
            </>
          )}
        </CardContent>
      </Card>

      {(o.limited || open) && (
        <>
      <div role="tablist" aria-label="Tipo" className="flex flex-wrap gap-1 rounded-xl bg-muted p-1">
        {KINDS.map((k) => {
          const s = o.kinds[k.kind]
          const on = kind === k.kind
          return (
            <button
              key={k.kind}
              type="button"
              role="tab"
              aria-selected={on}
              onClick={() => setKind(k.kind)}
              className={cn(
                'flex h-11 items-center gap-2 rounded-lg px-4 text-sm font-medium transition-colors',
                on ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground',
              )}
            >
              {k.label}
              {o.limited && (
                <span className="tabular text-xs text-muted-foreground">
                  {s.used}/{s.limit}
                </span>
              )}
              {s.locked > 0 && <Lock className="size-3.5 text-warning" aria-label={`${s.locked} bloqueados`} />}
            </button>
          )
        })}
      </div>
      <KindChooser key={kind} kind={kind} labels={KINDS.find((k) => k.kind === kind)!} />
        </>
      )}
    </div>
  )
}

function KindChooser({ kind, labels }: { kind: FreeKind; labels: (typeof KINDS)[number] }) {
  const q = useFreeKindItems(kind)
  const save = useChooseFreeActives(kind)
  const [picked, setPicked] = useState<Set<number> | null>(null)
  const [search, setSearch] = useState('')

  const items = useMemo(() => q.data?.items ?? [], [q.data])
  const current = useMemo(() => new Set(items.filter((i) => i.active).map((i) => i.id)), [items])
  const sel = picked ?? current
  const s = q.data?.status
  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase()
    const list = term ? items.filter((i) => i.name.toLowerCase().includes(term)) : items
    // Active first, then by age (id) — the same order the default uses.
    return [...list].sort((a, b) => Number(sel.has(b.id)) - Number(sel.has(a.id)) || a.id - b.id)
  }, [items, search, sel])

  if (!q.data || !s) return <Skeleton className="h-80 rounded-2xl" />

  const removed = [...current].filter((id) => !sel.has(id))
  const added = [...sel].filter((id) => !current.has(id))
  const dirty = removed.length > 0 || added.length > 0
  const isSwap = s.limited && removed.length > 0
  const blocked = isSwap && !!s.next_swap_at
  const full = sel.size >= s.limit
  const needsAdmin = kind === 'users' && !items.some((i) => i.is_admin && sel.has(i.id))

  const toggle = (item: FreeItem) => {
    const next = new Set(sel)
    if (next.has(item.id)) next.delete(item.id)
    else if (!full) next.add(item.id)
    setPicked(next)
  }

  return (
    <Card className="rounded-2xl">
      <CardHeader className="gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <CardTitle className="font-heading text-base">
            {s.limited ? null : 'Se mantendrían '}
            <span className="tabular" data-testid="free-count">
              {sel.size}/{s.limit}
            </span>{' '}
            {s.limited ? `${labels.many} activos` : labels.many}
          </CardTitle>
          {s.limited ? (
            <Badge variant="outline" className="gap-1">
              <Lock className="size-3" /> {s.locked} bloqueados
            </Badge>
          ) : (
            <Badge className="gap-1">
              <Sparkles className="size-3" /> Pro: todo activo
            </Badge>
          )}
          {!s.custom && <span className="text-xs text-muted-foreground">Por defecto: los más antiguos</span>}
        </div>
        {s.next_swap_at && (
          <p className="flex items-center gap-2 text-sm text-warning-foreground dark:text-warning">
            <Clock className="size-4" /> Próximo cambio por uno bloqueado: {fmtDateTime(s.next_swap_at)}. Mientras tanto
            podés sumar en lugares libres.
          </p>
        )}
        <div className="relative max-w-sm">
          <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            className="h-11 pl-9"
            placeholder={`Buscar ${labels.one}…`}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {!items.length ? (
          <p className="text-sm text-muted-foreground">No hay {labels.many} cargados.</p>
        ) : (
          <ul className="grid max-h-[28rem] gap-2 overflow-y-auto pr-1 sm:grid-cols-2">
            {filtered.map((item) => {
              const on = sel.has(item.id)
              const disabled = !on && full
              return (
                <li key={item.id}>
                  <button
                    type="button"
                    role="checkbox"
                    aria-checked={on}
                    disabled={disabled}
                    onClick={() => toggle(item)}
                    className={cn(
                      'flex min-h-12 w-full items-center gap-3 rounded-xl border px-3 py-2 text-left transition-colors',
                      on ? 'border-primary bg-primary/10' : 'hover:bg-muted',
                      disabled && 'cursor-not-allowed opacity-50 hover:bg-transparent',
                    )}
                  >
                    <span
                      className={cn(
                        'flex size-6 shrink-0 items-center justify-center rounded-md border',
                        on ? 'border-primary bg-primary text-primary-foreground' : 'border-input',
                      )}
                    >
                      {on ? <Check className="size-4" /> : s.limited ? <Lock className="size-3.5 text-muted-foreground" /> : <Pause className="size-3.5 text-muted-foreground" />}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-medium">{item.name}</span>
                      {item.detail && <span className="block truncate text-xs text-muted-foreground">{detail(kind, item)}</span>}
                      {!on && !s.limited && <span className="block truncate text-xs text-muted-foreground">Quedaría en pausa en el plan gratuito</span>}
                    </span>
                    {item.is_admin && <Badge variant="outline">Admin</Badge>}
                  </button>
                </li>
              )
            })}
          </ul>
        )}
        <div className="flex flex-wrap items-center justify-end gap-3 border-t pt-4">
          {needsAdmin && <span className="text-sm text-destructive">Tiene que quedar al menos un administrador.</span>}
          {blocked && <span className="text-sm text-destructive">Todavía no podés sacar activos (espera entre cambios).</span>}
          {isSwap && !blocked && (
            <span className="text-sm text-muted-foreground">
              Sacar un activo cuenta como cambio: el próximo va a tener que esperar.
            </span>
          )}
          {dirty && (
            <Button variant="outline" className="h-11" onClick={() => setPicked(null)}>
              Deshacer
            </Button>
          )}
          <Button
            variant={s.limited ? 'default' : 'secondary'}
            className="h-11 px-5"
            disabled={!dirty || blocked || needsAdmin || save.isPending}
            onClick={() => save.mutate([...sel], { onSuccess: () => setPicked(null) })}
          >
            {s.limited ? 'Guardar activos' : 'Guardar selección'}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

const ROLE: Record<string, string> = { admin: 'Administrador', encargado: 'Encargado', cajero: 'Cajero', barista: 'Barista' }

function detail(kind: FreeKind, item: FreeItem) {
  if (kind === 'users') return ROLE[item.detail ?? ''] ?? item.detail
  if (kind === 'stock_items') return `Unidad: ${item.detail}`
  return item.detail
}
