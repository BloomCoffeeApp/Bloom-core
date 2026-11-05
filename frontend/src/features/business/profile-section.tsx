import { ArrowRightLeft, Eye, EyeOff, Info, Loader2, SlidersHorizontal } from 'lucide-react'
import { useMemo, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Skeleton } from '@/components/ui/skeleton'
import { hasFeature, useLicense } from '@/features/license/api'
import { SettingsCard } from '@/features/settings/form'

import { resolveModules, useBusinessModules, useSaveProfile } from './api'
import { type Overrides, toggleOverride } from './meta'
import { ModuleToggles, ProfileIcon, ProfilePicker } from './profile-picker'
import type { BusinessModules, ModuleDef, ProfileKey } from './types'

function ChangeProfileDialog({
  info,
  customize: startCustomizing,
  onClose,
}: {
  info: BusinessModules
  customize: boolean
  onClose: () => void
}) {
  const save = useSaveProfile()
  const license = useLicense()
  const [profile, setProfile] = useState<ProfileKey>(info.profile)
  const [overrides, setOverrides] = useState<Overrides>(info.overrides)
  const [customizing, setCustomizing] = useState(startCustomizing)
  const def = info.profiles.find((p) => p.key === profile) ?? info.profiles[0]
  const next = useMemo(() => resolveModules(info.catalog, def.modules, overrides), [info.catalog, def, overrides])
  const appear = info.catalog.filter((m) => !info.modules[m.key] && next[m.key])
  const disappear = info.catalog.filter((m) => info.modules[m.key] && !next[m.key])
  const unchanged = profile === info.profile && !appear.length && !disappear.length

  const pick = (key: ProfileKey) => {
    setProfile(key)
    setOverrides(key === info.profile ? info.overrides : {})
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[90svh] overflow-y-auto sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle className="font-heading text-xl">Cambiar tipo de negocio</DialogTitle>
          <DialogDescription>
            Elegí el que más se parece a tu local: la app muestra solo lo que usás. Podés cambiarlo cuando quieras.
          </DialogDescription>
        </DialogHeader>
        <ProfilePicker profiles={info.profiles} value={profile} onChange={pick} current={info.profile} />

        <div className="grid gap-3 sm:grid-cols-2" data-testid="profile-preview">
          <PreviewList title="Van a aparecer" icon={Eye} tone="text-success" items={appear} empty="Nada nuevo." />
          <PreviewList title="Se van a ocultar" icon={EyeOff} tone="text-muted-foreground" items={disappear} empty="Nada se oculta." />
        </div>
        <p className="flex items-start gap-2 rounded-xl bg-muted/50 p-3 text-sm text-muted-foreground">
          <Info className="mt-0.5 size-4 shrink-0" />
          Ocultar no borra nada: ventas, productos, clientes y configuraciones quedan guardados y vuelven tal cual si
          lo activás de nuevo.
        </p>

        {customizing ? (
          <div className="space-y-2">
            <p className="text-sm font-medium">Personalizar módulos</p>
            <ModuleToggles
              catalog={info.catalog}
              modules={next}
              onToggle={(k, on) => setOverrides((o) => toggleOverride(info.catalog, o, k, on))}
              isLocked={(m) => !!(m.feature && license.data && !hasFeature(license.data, m.feature))}
            />
          </div>
        ) : (
          <Button variant="outline" className="h-11 w-fit" onClick={() => setCustomizing(true)}>
            <SlidersHorizontal /> Personalizar módulos
          </Button>
        )}

        <DialogFooter className="gap-2">
          <Button variant="ghost" className="h-11" onClick={onClose}>
            Cancelar
          </Button>
          <Button
            className="h-11"
            disabled={unchanged || save.isPending}
            onClick={() => save.mutate({ profile, modules: overrides }, { onSuccess: onClose })}
          >
            {save.isPending && <Loader2 className="animate-spin" />} Guardar cambios
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function PreviewList({
  title,
  icon: Icon,
  tone,
  items,
  empty,
}: {
  title: string
  icon: typeof Eye
  tone: string
  items: ModuleDef[]
  empty: string
}) {
  return (
    <div className="rounded-2xl border p-3">
      <p className={`mb-2 flex items-center gap-2 text-sm font-medium ${tone}`}>
        <Icon className="size-4" /> {title}
      </p>
      {items.length ? (
        <ul className="flex flex-wrap gap-1.5">
          {items.map((m) => (
            <li key={m.key} className="rounded-full border bg-background px-2.5 py-0.5 text-xs">
              {m.label}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-xs text-muted-foreground">{empty}</p>
      )}
    </div>
  )
}

/** Configuración → Negocio: the business type, what it shows, and "Cambiar tipo de negocio". */
export function BusinessProfileSection() {
  const q = useBusinessModules()
  const [dialog, setDialog] = useState<null | { customize: boolean }>(null)
  if (!q.data) return <Skeleton className="h-48 rounded-2xl" />
  const info = q.data
  const def = info.profiles.find((p) => p.key === info.profile)
  const shown = info.catalog.filter((m) => info.modules[m.key])
  const hidden = info.catalog.filter((m) => !info.modules[m.key])
  const customized = Object.keys(info.overrides).length > 0

  return (
    <SettingsCard
      title="Tipo de negocio"
      description="Define qué secciones ves en el menú, el inicio, la configuración y el punto de venta."
      footer={
        <>
          <Button variant="outline" className="h-9" onClick={() => setDialog({ customize: true })}>
            <SlidersHorizontal /> Personalizar
          </Button>
          <Button className="h-9" onClick={() => setDialog({ customize: false })}>
            <ArrowRightLeft /> Cambiar tipo de negocio
          </Button>
        </>
      }
    >
      <div className="flex items-start gap-3" data-testid="current-profile">
        <span className="flex size-12 shrink-0 items-center justify-center rounded-xl bg-primary text-primary-foreground">
          <ProfileIcon profile={info.profile} className="size-6" />
        </span>
        <div className="grid gap-0.5">
          <p className="font-medium">
            {def?.label ?? info.profile}
            {customized && <span className="ml-2 text-xs font-normal text-muted-foreground">(personalizado)</span>}
          </p>
          <p className="text-sm text-muted-foreground">{def?.description}</p>
        </div>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <PreviewList title="Se muestran" icon={Eye} tone="text-foreground" items={shown} empty="—" />
        <PreviewList title="Ocultos" icon={EyeOff} tone="text-muted-foreground" items={hidden} empty="Ninguno: se ve todo." />
      </div>
      {dialog && <ChangeProfileDialog info={info} customize={dialog.customize} onClose={() => setDialog(null)} />}
    </SettingsCard>
  )
}
