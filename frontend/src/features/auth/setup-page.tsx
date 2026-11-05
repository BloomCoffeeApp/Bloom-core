import { useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, SlidersHorizontal, Sparkles } from 'lucide-react'
import { useMemo, useState } from 'react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { api } from '@/lib/api'
import { type AuthUser, useAuth } from '@/lib/auth'
import { Logo } from '@/components/logo'
import { resolveModules, useBusinessCatalog } from '@/features/business/api'
import { type Overrides, toggleOverride } from '@/features/business/meta'
import { ModuleToggles, ProfilePicker } from '@/features/business/profile-picker'
import type { ProfileKey } from '@/features/business/types'
import { BRAND } from '@/lib/brand'

export function SetupPage() {
  const { completeLogin } = useAuth()
  const qc = useQueryClient()
  const [business, setBusiness] = useState('')
  const [name, setName] = useState('')
  const [pin, setPin] = useState('')
  const [pin2, setPin2] = useState('')
  const [demo, setDemo] = useState(true)
  const [busy, setBusy] = useState(false)
  // Step 2: business type (decides which sections the app shows; changeable later in Configuración).
  const [step, setStep] = useState<1 | 2>(1)
  const catalog = useBusinessCatalog()
  const [profile, setProfile] = useState<ProfileKey | null>(null)
  const [overrides, setOverrides] = useState<Overrides>({})
  const [customizing, setCustomizing] = useState(false)
  const def = catalog.data?.profiles.find((p) => p.key === profile)
  const modules = useMemo(
    () => (catalog.data && def ? resolveModules(catalog.data.catalog, def.modules, overrides) : null),
    [catalog.data, def, overrides],
  )

  const valid = business.trim() && name.trim() && /^\d{4,6}$/.test(pin) && pin === pin2

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!valid) return
    // Without the catalog (old server) the wizard skips the business type: everything is shown.
    if (step === 1 && !catalog.isError) {
      setStep(2)
      return
    }
    if (step === 2 && !profile) return
    setBusy(true)
    try {
      const res = await api.post<{ token: string; user: AuthUser }>('/setup', {
        business_name: business.trim(),
        admin_name: name.trim(),
        admin_pin: pin,
        load_demo: demo,
        ...(profile ? { profile, modules: overrides } : {}),
      })
      completeLogin(res)
      await qc.invalidateQueries()
      toast.success('¡Listo! Tu cafetería está configurada.')
    } catch (err) {
      toast.error((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const digits = (v: string) => v.replace(/\D/g, '')

  return (
    <div className="flex min-h-svh items-center justify-center bg-background p-4">
      <Card className={step === 2 ? 'w-full max-w-3xl rounded-3xl shadow-xl' : 'w-full max-w-lg rounded-3xl shadow-xl'}>
        <CardHeader className="text-center">
          <Logo className="mx-auto mb-2 size-16 rounded-2xl" />
          <CardTitle className="font-heading text-2xl">
            {step === 1 ? `Bienvenido a ${BRAND.name}` : '¿Qué tipo de negocio tenés?'}
          </CardTitle>
          <CardDescription>
            {step === 1
              ? 'Configuremos tu cafetería en un minuto.'
              : 'Así te mostramos solo lo que usás. Podés cambiarlo cuando quieras en Configuración → Negocio, sin perder datos.'}
          </CardDescription>
          {!catalog.isError && <p className="text-xs text-muted-foreground">Paso {step} de 2</p>}
        </CardHeader>
        <CardContent>
          <form onSubmit={submit} className="space-y-4">
            {step === 2 && catalog.data ? (
              <>
                <ProfilePicker
                  profiles={catalog.data.profiles}
                  value={profile}
                  onChange={(k) => {
                    setProfile(k)
                    setOverrides({})
                  }}
                />
                {modules &&
                  (customizing ? (
                    <div className="space-y-2">
                      <p className="text-sm font-medium">Personalizar módulos</p>
                      <ModuleToggles
                        catalog={catalog.data.catalog}
                        modules={modules}
                        onToggle={(k, on) => setOverrides((o) => toggleOverride(catalog.data!.catalog, o, k, on))}
                      />
                    </div>
                  ) : (
                    <Button type="button" variant="outline" className="h-11" onClick={() => setCustomizing(true)}>
                      <SlidersHorizontal /> Personalizar módulos
                    </Button>
                  ))}
                <div className="flex gap-2">
                  <Button type="button" variant="ghost" size="lg" className="h-11" onClick={() => setStep(1)}>
                    <ArrowLeft /> Volver
                  </Button>
                  <Button type="submit" size="lg" className="h-11 flex-1" disabled={!profile || busy}>
                    {busy ? 'Configurando…' : 'Empezar'}
                  </Button>
                </div>
              </>
            ) : (
              <>
                <div className="space-y-2">
                  <Label htmlFor="biz">Nombre de la cafetería</Label>
                  <Input id="biz" value={business} onChange={(e) => setBusiness(e.target.value)} autoFocus />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="name">Tu nombre (administrador)</Label>
                  <Input id="name" value={name} onChange={(e) => setName(e.target.value)} />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-2">
                    <Label htmlFor="pin">PIN (4 a 6 números)</Label>
                    <Input id="pin" type="password" inputMode="numeric" maxLength={6} value={pin}
                      onChange={(e) => setPin(digits(e.target.value))} />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="pin2">Repetir PIN</Label>
                    <Input id="pin2" type="password" inputMode="numeric" maxLength={6} value={pin2}
                      onChange={(e) => setPin2(digits(e.target.value))} />
                  </div>
                </div>
                {pin2 && pin !== pin2 && <p className="text-sm text-destructive">Los PIN no coinciden</p>}
                <label className="flex items-start gap-3 rounded-xl border bg-muted/40 p-3">
                  <Switch checked={demo} onCheckedChange={setDemo} className="mt-0.5" />
                  <span className="text-sm">
                    <span className="flex items-center gap-1 font-medium">
                      <Sparkles className="size-4 text-primary" /> Cargar datos de ejemplo
                    </span>
                    <span className="text-muted-foreground">
                      Menú, insumos, recetas, clientes y 3 meses de ventas ficticias para explorar la app. Usuarios demo:
                      Caja (1111), Barista (2222), Encargado (3333).
                    </span>
                  </span>
                </label>
                <Button type="submit" size="lg" className="h-11 w-full" disabled={!valid || busy}>
                  {busy ? 'Configurando…' : catalog.isError ? 'Empezar' : 'Siguiente'}
                </Button>
              </>
            )}
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
