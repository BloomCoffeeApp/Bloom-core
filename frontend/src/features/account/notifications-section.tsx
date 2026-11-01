import { Lock, WifiOff } from 'lucide-react'

import { Switch } from '@/components/ui/switch'

import { CardSkeleton, SettingsCard, SwitchRow } from '../settings/form'
import { useEmailPreferences, useSaveEmailPreferences } from './api'
import type { EmailCategory } from './types'

/** Shown (disabled) while offline or without a server, so the owner knows what exists. */
const FALLBACK: EmailCategory[] = [
  { key: 'news', label: 'Novedades y promociones', description: 'Ofertas, lanzamientos y noticias de Bloom.', locked: false },
  { key: 'updates', label: 'Actualizaciones del producto', description: 'Versiones nuevas, funciones y consejos de uso.', locked: false },
  {
    key: 'transactional',
    label: 'Cobros, cambios de precio y seguridad',
    description: 'Obligatorios: avisos de tu suscripción, cobros, cambios de precio, bajas y códigos de acceso.',
    locked: true,
  },
]

/** Configuración → Notificaciones: which emails the vendor sends to this business (live from the server). */
export function NotificationsSection() {
  const prefs = useEmailPreferences()
  const save = useSaveEmailPreferences()
  if (prefs.isLoading) return <CardSkeleton />
  const data = prefs.data
  const live = data?.available ? data : null
  const reason = live ? null : data && !data.available ? data.reason : 'No se pudieron consultar tus preferencias. Probá de nuevo en un rato.'
  const categories = live ? live.categories : FALLBACK

  return (
    <SettingsCard
      title="Notificaciones por mail"
      description={
        live?.email ? (
          <>
            Qué mails de Bloom te llegan a <span className="font-medium break-all text-foreground">{live.email}</span>.
          </>
        ) : (
          'Qué mails de Bloom querés recibir.'
        )
      }
    >
      {reason && (
        <div
          className="flex items-start gap-3 rounded-xl border border-dashed p-4 text-sm text-muted-foreground"
          role="status"
          data-testid="prefs-unavailable"
        >
          <WifiOff className="mt-0.5 size-4 shrink-0" />
          <p>{reason}</p>
        </div>
      )}
      <div className="space-y-3">
        {categories.map((c) => {
          const checked = c.locked ? true : live ? live.preferences[c.key] : false
          return (
            <SwitchRow
              key={c.key}
              title={c.label}
              description={
                c.locked ? (
                  <span className="inline-flex items-start gap-1.5">
                    <Lock className="mt-0.5 size-3.5 shrink-0" />
                    {c.description}
                  </span>
                ) : (
                  c.description
                )
              }
              control={
                <Switch
                  aria-label={c.label}
                  checked={checked}
                  disabled={c.locked || !live || save.isPending}
                  onCheckedChange={(v) => save.mutate({ [c.key]: v })}
                />
              }
            />
          )
        })}
      </div>
      <p className="text-xs text-muted-foreground">
        Los mails de cobros y cambios de precio son obligatorios por ley. También podés darte de baja con el link al pie de
        cada mail.
      </p>
    </SettingsCard>
  )
}
