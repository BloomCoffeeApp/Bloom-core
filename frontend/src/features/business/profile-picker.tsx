import { Bike, Check, Coffee, ShoppingBag, Store, UtensilsCrossed } from 'lucide-react'

import { Switch } from '@/components/ui/switch'
import { ProBadge } from '@/features/license/pro-gate'
import { cn } from '@/lib/utils'

import { CHANNEL_MODULES } from './api'
import type { ModuleDef, ModuleGroup, ModuleKey, ProfileDef, ProfileKey } from './types'

/** Icon of a business type; profiles added later in the backend get a generic one. */
export function ProfileIcon({ profile, className }: { profile: ProfileKey; className?: string }) {
  switch (profile) {
    case 'takeaway':
      return <ShoppingBag className={className} />
    case 'small':
      return <Coffee className={className} />
    case 'salon':
      return <UtensilsCrossed className={className} />
    case 'delivery':
      return <Bike className={className} />
    default:
      return <Store className={className} />
  }
}

/** Big cards to choose the business type (setup wizard and Configuración → Negocio). */
export function ProfilePicker({
  profiles,
  value,
  onChange,
  current,
}: {
  profiles: ProfileDef[]
  value: ProfileKey | null
  onChange: (key: ProfileKey) => void
  /** The profile in use (marked "Actual"). */
  current?: ProfileKey
}) {
  return (
    <div className="grid gap-3 sm:grid-cols-2" role="radiogroup" aria-label="Tipo de negocio">
      {profiles.map((p) => {
        const selected = value === p.key
        return (
          <button
            key={p.key}
            type="button"
            role="radio"
            aria-checked={selected}
            data-testid={`profile-${p.key}`}
            onClick={() => onChange(p.key)}
            className={cn(
              'relative flex min-h-24 items-start gap-3 rounded-2xl border p-4 text-left transition-colors',
              selected ? 'border-primary bg-primary/5 ring-2 ring-primary/30' : 'hover:bg-muted/50',
            )}
          >
            <span
              className={cn(
                'flex size-11 shrink-0 items-center justify-center rounded-xl',
                selected ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground',
              )}
            >
              <ProfileIcon profile={p.key} className="size-5" />
            </span>
            <span className="grid gap-0.5">
              <span className="flex flex-wrap items-center gap-2 font-medium">
                {p.label}
                {current === p.key && (
                  <span className="rounded-full bg-muted px-2 text-[11px] font-medium text-muted-foreground">Actual</span>
                )}
              </span>
              <span className="text-sm text-muted-foreground">{p.description}</span>
            </span>
            {selected && <Check className="absolute top-3 right-3 size-4 text-primary" />}
          </button>
        )
      })}
    </div>
  )
}

const GROUP_LABEL: Record<ModuleGroup, string> = {
  venta: 'Cómo vendés',
  operacion: 'Barra y cocina',
  gestion: 'Gestión',
  clientes: 'Clientes y marketing',
}

/** "Personalizar": one switch per module, grouped. A module whose requirement is off can't be turned on. */
export function ModuleToggles({
  catalog,
  modules,
  onToggle,
  isLocked,
}: {
  catalog: ModuleDef[]
  modules: Record<ModuleKey, boolean>
  onToggle: (key: ModuleKey, on: boolean) => void
  /** Pro badge on modules the license doesn't include (omitted in the setup wizard: no license yet). */
  isLocked?: (m: ModuleDef) => boolean
}) {
  const labels = Object.fromEntries(catalog.map((m) => [m.key, m.label])) as Record<ModuleKey, string>
  const channelsOn = CHANNEL_MODULES.filter((c) => modules[c]).length
  return (
    <div className="grid gap-4 md:grid-cols-2">
      {(Object.keys(GROUP_LABEL) as ModuleGroup[]).map((g) => {
        const items = catalog.filter((m) => m.group === g)
        if (!items.length) return null
        return (
          <fieldset key={g} className="space-y-1 rounded-2xl border p-3">
            <legend className="px-1 text-xs font-medium tracking-wide text-muted-foreground uppercase">
              {GROUP_LABEL[g]}
            </legend>
            {items.map((m) => {
              const missing = m.requires.filter((r) => !modules[r])
              const lastChannel = CHANNEL_MODULES.includes(m.key) && modules[m.key] && channelsOn === 1
              const locked = isLocked?.(m) ?? false
              const id = `module-${m.key}`
              return (
                <label
                  key={m.key}
                  htmlFor={id}
                  className={cn(
                    'flex min-h-12 cursor-pointer items-center gap-3 rounded-xl px-2 py-1.5 hover:bg-muted/50',
                    missing.length > 0 && 'cursor-default opacity-60',
                  )}
                >
                  <span className="grid min-w-0 flex-1 gap-0.5">
                    <span className="flex items-center gap-2 text-sm font-medium">
                      {m.label}
                      {locked && <ProBadge />}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {missing.length > 0
                        ? `Necesita «${missing.map((r) => labels[r]).join('», «')}».`
                        : lastChannel
                          ? 'Tiene que quedar al menos un canal de venta.'
                          : m.description}
                    </span>
                  </span>
                  <Switch
                    id={id}
                    checked={modules[m.key]}
                    disabled={missing.length > 0 || lastChannel}
                    onCheckedChange={(v) => onToggle(m.key, v)}
                    aria-label={m.label}
                  />
                </label>
              )
            })}
          </fieldset>
        )
      })}
    </div>
  )
}
