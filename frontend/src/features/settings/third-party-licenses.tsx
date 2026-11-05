import { useQuery } from '@tanstack/react-query'
import { FileText, Search } from 'lucide-react'
import { useMemo, useState } from 'react'

import { EmptyState } from '@/components/empty-state'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'

// Mirrors app/schemas/third_party.py (kept apart from settings/types.ts: this screen is self-contained).
export interface ThirdPartyPackage {
  name: string
  version: string
  license: string
  source: 'frontend' | 'backend' | 'runtime' | string
  homepage: string
  copyright: string[]
  text: string
  note: string
}

export interface ThirdPartyNotices {
  available: boolean
  generated_at: string | null
  packages: ThirdPartyPackage[]
}

const SOURCE_LABEL: Record<string, string> = { frontend: 'Interfaz', backend: 'Servidor local', runtime: 'Sistema' }

function useThirdPartyNotices(enabled: boolean) {
  return useQuery({
    queryKey: ['settings', 'third-party-licenses'],
    queryFn: () => api.get<ThirdPartyNotices>('/system/third-party-licenses'),
    enabled,
    staleTime: Infinity,
  })
}

function LicensesBrowser({ data }: { data: ThirdPartyNotices }) {
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState<string | null>(null)
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return data.packages
    return data.packages.filter((p) => `${p.name} ${p.license} ${p.copyright.join(' ')}`.toLowerCase().includes(q))
  }, [data.packages, query])
  const key = (p: ThirdPartyPackage) => `${p.source}:${p.name}`
  const current = filtered.find((p) => key(p) === selected) ?? filtered[0]

  return (
    <div className="grid min-h-0 gap-3 md:grid-cols-[minmax(0,16rem)_minmax(0,1fr)]">
      <div className="flex min-h-0 flex-col gap-2">
        <div className="relative">
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Buscar paquete o licencia…"
            aria-label="Buscar licencias"
            className="pl-8"
          />
        </div>
        <p className="text-xs text-muted-foreground">
          {filtered.length} de {data.packages.length} componentes
        </p>
        <ul className="max-h-48 overflow-y-auto rounded-xl border md:max-h-[55svh]" aria-label="Componentes de terceros">
          {filtered.map((p) => (
            <li key={key(p)}>
              <button
                type="button"
                onClick={() => setSelected(key(p))}
                className={cn(
                  'flex w-full flex-col items-start gap-0.5 border-b px-3 py-2 text-left text-sm last:border-b-0 hover:bg-muted',
                  current && key(current) === key(p) && 'bg-primary/10 text-primary',
                )}
              >
                <span className="w-full truncate font-medium">{p.name}</span>
                <span className="text-xs text-muted-foreground">
                  {p.version && `${p.version} · `}
                  {p.license}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </div>
      <div className="flex min-h-0 min-w-0 flex-col gap-2">
        {current ? (
          <>
            <div className="flex flex-wrap items-center gap-2">
              <p className="font-medium" data-testid="third-party-current">
                {current.name} {current.version}
              </p>
              <Badge variant="secondary">{current.license}</Badge>
              <Badge variant="outline">{SOURCE_LABEL[current.source] ?? current.source}</Badge>
            </div>
            {current.homepage && <p className="truncate text-xs text-muted-foreground">{current.homepage}</p>}
            {current.note && <p className="text-xs text-muted-foreground">{current.note}</p>}
            <pre className="max-h-[45svh] overflow-auto rounded-xl border bg-muted/40 p-3 text-xs whitespace-pre-wrap md:max-h-[55svh]">
              {current.text || 'El paquete no incluye el texto de la licencia.'}
            </pre>
          </>
        ) : (
          <EmptyState icon={Search} title="Sin resultados" description="Probá con otro nombre o licencia." />
        )}
      </div>
    </div>
  )
}

export function ThirdPartyLicenses() {
  const [open, setOpen] = useState(false)
  const notices = useThirdPartyNotices(open)
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <div className="flex items-start gap-3 rounded-xl border p-4">
        <FileText className="mt-0.5 size-5 text-muted-foreground" />
        <div className="flex-1 text-sm">
          <p className="font-medium">Licencias de terceros</p>
          <p className="text-muted-foreground">Componentes de código abierto que usa la app y sus licencias.</p>
        </div>
        <DialogTrigger asChild>
          <Button variant="outline" size="sm">
            Ver licencias
          </Button>
        </DialogTrigger>
      </div>
      <DialogContent className="max-h-[90svh] overflow-y-auto sm:max-w-4xl">
        <DialogHeader>
          <DialogTitle>Licencias de terceros</DialogTitle>
          <DialogDescription>
            Gracias a quienes hacen estos proyectos de código abierto. Cada uno se usa según su licencia.
          </DialogDescription>
        </DialogHeader>
        {notices.isLoading ? (
          <Skeleton className="h-64 w-full" />
        ) : notices.data?.available ? (
          <LicensesBrowser data={notices.data} />
        ) : (
          <EmptyState
            icon={FileText}
            title="Lista no disponible"
            description="La lista de licencias se genera al compilar el instalador (build/third_party_notices.py)."
          />
        )}
      </DialogContent>
    </Dialog>
  )
}
