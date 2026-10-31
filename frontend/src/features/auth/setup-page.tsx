import { useQueryClient } from '@tanstack/react-query'
import { Sparkles } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { api } from '@/lib/api'
import { type AuthUser, useAuth } from '@/lib/auth'
import { Logo } from '@/components/logo'
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

  const valid = business.trim() && name.trim() && /^\d{4,6}$/.test(pin) && pin === pin2

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!valid) return
    setBusy(true)
    try {
      const res = await api.post<{ token: string; user: AuthUser }>('/setup', {
        business_name: business.trim(),
        admin_name: name.trim(),
        admin_pin: pin,
        load_demo: demo,
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
      <Card className="w-full max-w-lg rounded-3xl shadow-xl">
        <CardHeader className="text-center">
          <Logo className="mx-auto mb-2 size-16 rounded-2xl" />
          <CardTitle className="font-heading text-2xl">Bienvenido a {BRAND.name}</CardTitle>
          <CardDescription>Configuremos tu cafetería en un minuto.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={submit} className="space-y-4">
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
              {busy ? 'Configurando…' : 'Empezar'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
