import { useQuery } from '@tanstack/react-query'
import { FlaskConical } from 'lucide-react'

import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { api } from '@/lib/api'

interface DemoInfo {
  /** This browser's sandbox exists (false: never created here or deleted after being idle). */
  session: boolean
  start_url: string
  idle_hours: number
  site_url: string | null
  users: { name: string; pin: string; role: string }[]
}

interface Health {
  demo?: DemoInfo
}

/** Online demo only (server started with BLOOM_DEMO=1): a small pill that never goes away, so nobody
 * mistakes the demo for their real data. Renders nothing in the desktop app. */
export function DemoBanner() {
  const { data } = useQuery({
    queryKey: ['health'],
    queryFn: () => api.get<Health>('/health'),
    staleTime: 30_000,
    refetchInterval: (q) => (q.state.data?.demo ? 60_000 : false),
    refetchOnWindowFocus: true,
    retry: false,
  })
  const demo = data?.demo
  if (!demo) return null
  const hours = demo.idle_hours === 1 ? '1 hora' : `${demo.idle_hours} horas`
  if (!demo.session)
    return (
      <div
        role="alertdialog"
        aria-labelledby="demo-gone-title"
        className="fixed inset-0 z-[70] flex items-center justify-center bg-background/90 p-6 backdrop-blur-sm"
      >
        <div className="max-w-sm rounded-xl border bg-card p-6 text-center shadow-lg">
          <h2 id="demo-gone-title" className="font-heading text-xl font-semibold">
            Empezá tu demo
          </h2>
          <p className="mt-2 text-sm text-muted-foreground">
            Cada demo es solo tuya y se borra sola después de {hours} sin uso. Si ya tenías una, se borró: empezá
            otra con datos de ejemplo nuevos.
          </p>
          <a
            href={demo.start_url}
            className="mt-4 inline-flex h-11 items-center justify-center rounded-md bg-primary px-5 text-sm font-medium text-primary-foreground hover:bg-primary/90 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          >
            Empezar la demo
          </a>
        </div>
      </div>
    )
  return (
    // Phones: centered on top. Wider screens: in the header's empty stretch, clear of the search box.
    <div className="pointer-events-none fixed inset-x-0 top-1.5 z-[60] flex justify-center px-2 lg:top-4 lg:justify-end lg:pr-36">

      <Popover>
        <PopoverTrigger asChild>
          <button
            type="button"
            data-testid="demo-banner"
            className="pointer-events-auto flex max-w-full items-center gap-1.5 truncate rounded-full border border-warning/60 bg-warning px-3 py-1 text-xs font-semibold text-warning-foreground shadow-md focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          >
            <FlaskConical className="size-3.5 shrink-0" aria-hidden />
            <span className="truncate">Demo: los datos se borran solos</span>
          </button>
        </PopoverTrigger>
        <PopoverContent className="w-80 text-sm" align="center">
          <p className="font-medium">Esta demo es solo tuya.</p>
          <p className="mt-1 text-muted-foreground">
            Probá todo lo que quieras: nadie más ve tus cambios y se borran solos después de {hours} sin uso. Todas
            las funciones Pro están activas.
          </p>
          <p className="mt-3 font-medium">Para entrar</p>
          <ul className="mt-1 space-y-0.5">
            {demo.users.map((u) => (
              <li key={u.name} className="flex justify-between gap-2">
                <span>
                  {u.name} <span className="text-muted-foreground">({u.role})</span>
                </span>
                <span className="font-mono">PIN {u.pin}</span>
              </li>
            ))}
          </ul>
          {demo.site_url && (
            <a
              href={demo.site_url}
              className="mt-3 inline-flex font-medium text-primary underline-offset-4 hover:underline"
            >
              Descargá Bloom gratis
            </a>
          )}
        </PopoverContent>
      </Popover>
    </div>
  )
}
