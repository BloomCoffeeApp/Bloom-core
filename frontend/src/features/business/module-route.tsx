import { EyeOff, Loader2 } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'

import { Button } from '@/components/ui/button'
import { useAuth } from '@/lib/auth'

import { useModules, useSetModule } from './api'
import type { ModuleKey } from './types'

/**
 * Deep links keep working when a module is hidden for this business type: instead of the module,
 * a friendly page explains it and (admins) turns it back on in one click.
 */
export function ModuleRoute({ module, children }: { module: ModuleKey; children: ReactNode }) {
  const { on, ready } = useModules()
  if (!ready) return null
  if (on(module)) return <>{children}</>
  return <HiddenModule module={module} />
}

function HiddenModule({ module }: { module: ModuleKey }) {
  const { can } = useAuth()
  const { data } = useModules()
  const set = useSetModule()
  const def = data?.catalog.find((m) => m.key === module)
  const profile = data?.profiles.find((p) => p.key === data.profile)
  const label = def?.label ?? 'Este módulo'
  return (
    <div className="mx-auto max-w-xl py-10" data-testid="hidden-module">
      <div className="flex flex-col items-center gap-4 rounded-3xl border bg-card px-6 py-12 text-center shadow-xs">
        <div className="flex size-16 items-center justify-center rounded-2xl bg-muted text-muted-foreground">
          <EyeOff className="size-8" />
        </div>
        <div className="space-y-1.5">
          <h1 className="font-heading text-2xl font-semibold">Este módulo está oculto para tu tipo de negocio</h1>
          <p className="text-muted-foreground">
            <b className="text-foreground">{label}</b> no se muestra
            {profile ? ` en «${profile.label}»` : ''}. Tus datos siguen guardados: si lo activás, vuelve todo como estaba.
          </p>
        </div>
        {can('settings.manage') ? (
          <div className="flex flex-wrap justify-center gap-2">
            <Button className="h-11" onClick={() => set.mutate({ key: module, enabled: true })} disabled={set.isPending}>
              {set.isPending && <Loader2 className="animate-spin" />} Activarlo
            </Button>
            <Button variant="outline" className="h-11" asChild>
              <Link to="/config?tab=negocio">Cambiar tipo de negocio</Link>
            </Button>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">Pedile a un administrador que lo active en Configuración → Negocio.</p>
        )}
      </div>
    </div>
  )
}
