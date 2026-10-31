import { PackageSearch, Search, SlidersHorizontal, X } from 'lucide-react'
import { useMemo, useState, type KeyboardEvent, type RefObject } from 'react'

import { EmptyState } from '@/components/empty-state'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { fmtMoney } from '@/lib/format'
import { cn } from '@/lib/utils'

import { colorClasses } from './colors'
import type { PosCatalog, PosProduct } from './types'

const normalize = (s: string) => s.normalize('NFD').replace(/\p{Diacritic}/gu, '').toLowerCase()

const imageSrc = (path: string) => (/^(https?:|\/|data:)/.test(path) ? path : `/uploads/${path}`)

export function ProductGrid({
  catalog,
  loading,
  error,
  onPick,
  searchRef,
}: {
  catalog: PosCatalog | undefined
  loading: boolean
  error: Error | null
  onPick: (p: PosProduct) => void
  searchRef: RefObject<HTMLInputElement | null>
}) {
  const [q, setQ] = useState('')
  const [cat, setCat] = useState<number | 'all'>('all')

  const catColor = useMemo(() => new Map(catalog?.categories.map((c) => [c.id, c.color]) ?? []), [catalog])
  const products = useMemo(() => {
    let list = catalog?.products ?? []
    if (q.trim()) {
      const nq = normalize(q.trim())
      list = list.filter((p) => normalize(p.name).includes(nq))
    } else if (cat !== 'all') {
      list = list.filter((p) => p.category_id === cat)
    }
    return list
  }, [catalog, q, cat])

  const onSearchKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && products.length > 0 && q.trim()) {
      onPick(products[0])
      setQ('')
    } else if (e.key === 'Escape' && q) {
      e.stopPropagation()
      setQ('')
    }
  }

  return (
    <div className="flex min-h-0 flex-col gap-3 p-4">
      <div className="relative">
        <Search className="absolute top-1/2 left-4 size-5 -translate-y-1/2 text-muted-foreground" />
        <Input
          ref={searchRef}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={onSearchKey}
          placeholder="Buscá un producto… (F2)"
          className="h-14 rounded-2xl pr-12 pl-12 text-lg"
          aria-label="Buscar producto"
        />
        {q && (
          <button
            onClick={() => setQ('')}
            className="absolute top-1/2 right-3 flex size-9 -translate-y-1/2 items-center justify-center rounded-full text-muted-foreground hover:bg-muted"
            aria-label="Limpiar búsqueda"
          >
            <X className="size-5" />
          </button>
        )}
      </div>

      <div className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1">
        <button
          onClick={() => {
            setCat('all')
            setQ('')
          }}
          className={cn(
            'touch-target h-11 shrink-0 rounded-full border px-5 text-sm font-medium transition-colors',
            cat === 'all' && !q ? 'border-primary bg-primary text-primary-foreground' : 'bg-card hover:bg-muted',
          )}
        >
          Todo
        </button>
        {catalog?.categories.map((c) => (
          <button
            key={c.id}
            onClick={() => {
              setCat(c.id)
              setQ('')
            }}
            className={cn(
              'touch-target flex h-11 shrink-0 items-center gap-2 rounded-full border px-5 text-sm font-medium transition-colors',
              cat === c.id && !q ? 'border-primary bg-primary text-primary-foreground' : 'bg-card hover:bg-muted',
            )}
          >
            <span className={cn('size-2.5 rounded-full', colorClasses(c.color).dot)} />
            {c.name}
          </button>
        ))}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto pb-4">
        {loading ? (
          <div className="grid grid-cols-[repeat(auto-fill,minmax(150px,1fr))] gap-3">
            {Array.from({ length: 12 }).map((_, i) => (
              <Skeleton key={i} className="h-28 rounded-2xl" />
            ))}
          </div>
        ) : error ? (
          <EmptyState icon={PackageSearch} title="No se pudo cargar el catálogo" description={error.message} />
        ) : products.length === 0 ? (
          <EmptyState
            icon={PackageSearch}
            title={q ? 'Sin coincidencias' : 'No hay productos'}
            description={q ? `No encontramos “${q}”.` : 'Cargá productos en el catálogo para venderlos acá.'}
          />
        ) : (
          <div className="grid grid-cols-[repeat(auto-fill,minmax(150px,1fr))] gap-3">
            {products.map((p) => {
              const cls = colorClasses(p.color ?? catColor.get(p.category_id ?? -1))
              return (
                <button
                  key={p.id}
                  onClick={() => onPick(p)}
                  className={cn(
                    'group relative flex min-h-28 flex-col justify-between overflow-hidden rounded-2xl border p-3 text-left shadow-xs transition-all select-none active:scale-[0.97]',
                    cls.tile,
                  )}
                >
                  {p.image_path && (
                    <img src={imageSrc(p.image_path)} alt="" className="-mx-3 -mt-3 mb-2 h-20 w-[calc(100%+1.5rem)] object-cover" loading="lazy" />
                  )}
                  <span className="line-clamp-2 leading-tight font-semibold">{p.name}</span>
                  <span className="mt-2 flex items-end justify-between gap-2">
                    <span className="tabular text-lg font-semibold">{fmtMoney(p.price_cents, { short: true })}</span>
                    {p.modifier_groups.length > 0 && (
                      <SlidersHorizontal className="size-4 text-muted-foreground" aria-label="Con opciones" />
                    )}
                  </span>
                </button>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
