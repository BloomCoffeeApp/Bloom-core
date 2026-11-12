import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Delete, Lock } from 'lucide-react'
import { Suspense, useCallback, useEffect, useState } from 'react'

import { AVATAR_COLORS, initials } from '@/components/avatar-utils'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { api, ApiError } from '@/lib/api'
import { type AuthUser, useAuth } from '@/lib/auth'
import { ROLE_LABEL } from '@/lib/format'
import { cn } from '@/lib/utils'
import { Logo } from '@/components/logo'
import { BRAND } from '@/lib/brand'
import { proModules } from '@pro'

const KEYS = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '', '0', 'del']

export function LoginPage({ businessName }: { businessName?: string }) {
  const { login } = useAuth()
  const [selected, setSelected] = useState<AuthUser | null>(null)
  const [pin, setPin] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const { data: users, isLoading } = useQuery({
    queryKey: ['login-users'],
    queryFn: () => api.get<AuthUser[]>('/auth/users'),
  })

  const submit = useCallback(
    async (value: string) => {
      if (!selected || busy || value.length < 4) return
      setBusy(true)
      try {
        await login(selected.id, value)
      } catch (e) {
        setError(e instanceof ApiError && (e.status === 429 || e.status === 402) ? e.message : 'PIN incorrecto')
        setPin('')
      } finally {
        setBusy(false)
      }
    },
    [selected, login, busy],
  )

  const press = useCallback(
    (k: string) => {
      setError(null)
      if (k === 'del') return setPin((p) => p.slice(0, -1))
      if (k === 'ok') return void submit(pin)
      setPin((p) => (p + k).slice(0, 6))
    },
    [pin, submit],
  )

  useEffect(() => {
    if (!selected) return
    const onKey = (e: KeyboardEvent) => {
      if (/^\d$/.test(e.key)) press(e.key)
      else if (e.key === 'Backspace') press('del')
      else if (e.key === 'Enter') press('ok')
      else if (e.key === 'Escape') setSelected(null)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [selected, press])

  return (
    <div className="relative flex min-h-svh items-center justify-center overflow-hidden bg-background p-4">
      <div className="pointer-events-none absolute -top-40 -left-40 size-[480px] rounded-full bg-primary/15 blur-3xl" />
      <div className="pointer-events-none absolute -right-40 -bottom-40 size-[480px] rounded-full bg-warning/15 blur-3xl" />
      <div className="relative w-full max-w-md">
        <div className="mb-8 flex flex-col items-center gap-3 text-center">
          <Logo className="size-16 shadow-lg rounded-2xl" />
          <div>
            <h1 className="font-heading text-3xl font-semibold">{businessName || BRAND.name}</h1>
            <p className="text-sm text-muted-foreground">
              {selected ? `Hola ${selected.name.split(' ')[0]}, ingresá tu PIN` : '¿Quién está trabajando?'}
            </p>
          </div>
        </div>

        <div className="rounded-3xl border bg-card/80 p-6 shadow-xl backdrop-blur">
          {!selected ? (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              {isLoading &&
                Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-28 rounded-2xl" />)}
              {users?.map((u) => (
                <button
                  key={u.id}
                  disabled={u.locked}
                  title={u.locked ? 'Bloqueado en el plan gratuito: el administrador puede activarlo en «Elegí tus activos».' : undefined}
                  onClick={() => {
                    setSelected(u)
                    setPin('')
                  }}
                  className={cn(
                    'relative flex flex-col items-center gap-2 rounded-2xl border bg-background p-4 transition hover:-translate-y-0.5 hover:border-primary hover:shadow-md',
                    u.locked && 'cursor-not-allowed opacity-60 hover:translate-y-0 hover:border-border hover:shadow-none',
                  )}
                >
                  {u.locked && <Lock className="absolute top-2 right-2 size-4 text-warning" aria-label="Bloqueado" />}
                  <Avatar className="size-12">
                    <AvatarFallback className={cn('font-semibold', AVATAR_COLORS[u.color])}>
                      {initials(u.name)}
                    </AvatarFallback>
                  </Avatar>
                  <div className="text-center leading-tight">
                    <p className="text-sm font-medium">{u.name}</p>
                    <p className="text-xs text-muted-foreground">{u.role_name ?? ROLE_LABEL[u.role] ?? u.role}</p>
                  </div>
                </button>
              ))}
            </div>
          ) : (
            <div className="flex flex-col items-center gap-5">
              <div className="flex w-full items-center">
                <Button variant="ghost" size="sm" onClick={() => setSelected(null)}>
                  <ArrowLeft /> Cambiar usuario
                </Button>
              </div>
              <div className="flex h-6 gap-3">
                {Array.from({ length: Math.max(4, pin.length) }).map((_, i) => (
                  <span
                    key={i}
                    className={cn(
                      'size-4 rounded-full border-2 transition',
                      i < pin.length ? 'border-primary bg-primary' : 'border-muted-foreground/40',
                      error && 'border-destructive',
                    )}
                  />
                ))}
              </div>
              <p className={cn('h-5 text-sm', error ? 'text-destructive' : 'text-transparent')}>{error ?? '.'}</p>
              <div className="grid w-full max-w-xs grid-cols-3 gap-3">
                {KEYS.map((k) =>
                  k === '' ? (
                    <span key="spacer" />
                  ) : (
                    <button
                      key={k}
                      onClick={() => press(k)}
                      className="flex h-16 items-center justify-center rounded-2xl border bg-background text-2xl font-medium transition hover:bg-muted active:scale-95"
                      aria-label={k === 'del' ? 'Borrar' : k}
                    >
                      {k === 'del' ? <Delete className="size-6" /> : k}
                    </button>
                  ),
                )}
              </div>
              <Button
                size="lg"
                className="h-12 w-full max-w-xs text-base"
                disabled={pin.length < 4 || busy}
                onClick={() => submit(pin)}
              >
                Entrar
              </Button>
            </div>
          )}
        </div>
        {proModules.TimeClockButton && !selected && (
          <Suspense fallback={null}>
            <proModules.TimeClockButton />
          </Suspense>
        )}
        <p className="mt-6 text-center text-xs text-muted-foreground">{BRAND.name} · {BRAND.tagline}</p>
      </div>
    </div>
  )
}
