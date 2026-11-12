import { useQuery } from '@tanstack/react-query'
import { Download, FlaskConical, Hourglass, UserPlus } from 'lucide-react'
import { useEffect, useState } from 'react'

import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { api } from '@/lib/api'
import { setDemoMode } from '@/lib/demo'
import { cn } from '@/lib/utils'

interface DemoInfo {
  /** This browser's sandbox exists (false: never created here, deleted after being idle, or its time is over). */
  session: boolean
  /** Seconds until this demo is deleted no matter what (absolute lifetime). */
  expires_in_s: number | null
  /** Why the previous demo of this browser is gone. */
  ended: 'lifetime' | 'idle' | null
  start_url: string
  idle_hours: number
  max_lifetime_hours: number
  site_url: string | null
  signup_url: string | null
  users: { name: string; pin: string; role: string }[]
}

interface Health {
  demo?: DemoInfo
}

const hoursText = (h: number) => (h === 1 ? '1 hora' : `${h} horas`)

/** "45 min", "1 h 05 min", "menos de 1 min". */
function fmtLeft(seconds: number) {
  if (seconds < 60) return 'menos de 1 min'
  const m = Math.floor(seconds / 60)
  if (m < 60) return `${m} min`
  return `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, '0')} min`
}

const linkCls =
  'inline-flex h-11 w-full items-center justify-center gap-2 rounded-md px-5 text-sm font-medium whitespace-nowrap focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none'

/** Friendly end screen: the demo's time is over (or it was deleted when idle). */
function DemoEnded({ demo }: { demo: DemoInfo }) {
  const lifetime = demo.ended === 'lifetime'
  return (
    <div
      role="alertdialog"
      aria-labelledby="demo-gone-title"
      className="fixed inset-0 z-[70] flex items-center justify-center bg-background/90 p-6 backdrop-blur-sm"
    >
      <div className="max-w-md rounded-xl border bg-card p-6 text-center shadow-lg">
        <h2 id="demo-gone-title" className="font-heading text-xl font-semibold">
          {lifetime ? 'Tu demo terminó' : demo.ended === 'idle' ? 'Tu demo se borró' : 'Empezá tu demo'}
        </h2>
        <p className="mt-2 text-sm text-muted-foreground">
          {lifetime
            ? `Cada demo dura ${hoursText(demo.max_lifetime_hours)} y después se borra con todos sus datos. ¡Gracias por probar Bloom! Si te gustó, descargalo gratis: es la app completa, con tus datos en tu computadora y sin límite de tiempo.`
            : `Cada demo es solo tuya y se borra sola después de ${hoursText(demo.idle_hours)} sin uso (o a las ${hoursText(demo.max_lifetime_hours)}). ${demo.ended === 'idle' ? 'La tuya ya se borró: ' : ''}empezá una con datos de ejemplo nuevos.`}
        </p>
        <div className="mt-5 flex flex-col gap-2">
          {lifetime && demo.site_url && (
            <a href={demo.site_url} className={cn(linkCls, 'bg-primary text-primary-foreground hover:bg-primary/90')}>
              <Download className="size-4" /> Descargá Bloom gratis
            </a>
          )}
          {lifetime && demo.signup_url && (
            <a href={demo.signup_url} className={cn(linkCls, 'border bg-background hover:bg-muted')}>
              <UserPlus className="size-4" /> Crear mi cuenta
            </a>
          )}
          <a
            href={demo.start_url}
            className={cn(
              linkCls,
              lifetime ? 'text-primary underline-offset-4 hover:underline' : 'bg-primary text-primary-foreground hover:bg-primary/90',
            )}
          >
            {lifetime ? 'Empezar otra demo' : 'Empezar la demo'}
          </a>
        </div>
      </div>
    </div>
  )
}

/** Seconds left, ticking locally from the server's answer (never trusts the visitor's clock). */
function useCountdown(seconds: number | null, receivedAt: number) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (seconds == null) return
    const t = setInterval(() => setNow(Date.now()), 15_000)
    return () => clearInterval(t)
  }, [seconds])
  if (seconds == null) return null
  return Math.max(0, seconds - Math.floor((now - receivedAt) / 1000))
}

/** Online demo only (server started with BLOOM_DEMO=1): a small pill that never goes away, so nobody
 * mistakes the demo for their real data, with the time left. Renders nothing in the desktop app. */
export function DemoBanner() {
  const { data, dataUpdatedAt, refetch } = useQuery({
    queryKey: ['health'],
    queryFn: () => api.get<Health>('/health'),
    staleTime: 30_000,
    refetchInterval: (q) => (q.state.data?.demo ? 60_000 : false),
    refetchOnWindowFocus: true,
    retry: false,
  })
  const demo = data?.demo
  useEffect(() => setDemoMode(!!demo), [demo])
  const left = useCountdown(demo?.expires_in_s ?? null, dataUpdatedAt)
  useEffect(() => {
    if (left === 0) void refetch() // time's up: the server says it ended → end screen
  }, [left, refetch])
  if (!demo) return null
  if (!demo.session) return <DemoEnded demo={demo} />
  const soon = left != null && left <= 15 * 60
  return (
    // Phones: centered on top. Wider screens: in the header's empty stretch, clear of the search box.
    <div className="pointer-events-none fixed inset-x-0 top-1.5 z-[60] flex justify-center px-2 lg:top-4 lg:justify-end lg:pr-36">
      <Popover>
        <PopoverTrigger asChild>
          <button
            type="button"
            data-testid="demo-banner"
            className={cn(
              'pointer-events-auto flex max-w-full items-center gap-1.5 truncate rounded-full border px-3 py-1 text-xs font-semibold shadow-md focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none',
              soon ? 'border-destructive/60 bg-card text-destructive' : 'border-warning/60 bg-warning text-warning-foreground',
            )}
          >
            {left != null ? (
              <Hourglass className="size-3.5 shrink-0" aria-hidden />
            ) : (
              <FlaskConical className="size-3.5 shrink-0" aria-hidden />
            )}
            <span className="truncate" data-testid="demo-countdown">
              {left != null ? `Tu demo se borra en ${fmtLeft(left)}` : 'Demo: los datos se borran solos'}
            </span>
          </button>
        </PopoverTrigger>
        <PopoverContent className="w-80 text-sm" align="center">
          <p className="font-medium">Esta demo es solo tuya.</p>
          <p className="mt-1 text-muted-foreground">
            Probá todo lo que quieras: nadie más ve tus cambios. Dura {hoursText(demo.max_lifetime_hours)} como máximo (o{' '}
            {hoursText(demo.idle_hours)} sin uso) y después se borra. Todas las funciones Pro están activas; lo que imprimas sale marcado
            como DEMO.
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
            <a href={demo.site_url} className="mt-3 inline-flex font-medium text-primary underline-offset-4 hover:underline">
              Descargá Bloom gratis
            </a>
          )}
        </PopoverContent>
      </Popover>
    </div>
  )
}
