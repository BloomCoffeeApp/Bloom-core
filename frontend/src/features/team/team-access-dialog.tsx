import { Copy, Loader2, RefreshCw, Smartphone } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useAuth } from '@/lib/auth'
import { cn } from '@/lib/utils'

import { useRotateTeamCode, useSaveTeamConfig, useTeamInfo, useTeamQr } from './api'

function Notice({ children, tone = 'info' }: { children: React.ReactNode; tone?: 'info' | 'error' }) {
  return (
    <p role={tone === 'error' ? 'alert' : 'status'} className={cn('rounded-xl border p-3 text-sm', tone === 'error' ? 'border-destructive/40 bg-destructive/5 text-destructive' : 'border-warning/40 bg-warning/5')}>
      {children}
    </p>
  )
}

/** «QR para el equipo»: the code the staff scans with their phone to open Bloom Equipo (a Pro module). */
export function TeamAccessDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const { can } = useAuth()
  const info = useTeamInfo(open)
  const qr = useTeamQr(open && !!info.data?.url, info.data?.url ?? null)
  const rotate = useRotateTeamCode()
  const save = useSaveTeamConfig()
  const manage = can('orders.manage', 'settings.manage')

  const copy = async () => {
    if (!info.data?.url) return
    try {
      await navigator.clipboard.writeText(info.data.url)
      toast.success('Link copiado')
    } catch {
      toast.error('No se pudo copiar: seleccionalo y copialo a mano')
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Smartphone className="size-5" /> QR para el equipo
          </DialogTitle>
          <DialogDescription>
            Cada persona lo escanea con su celular (con el Wi-Fi del local), elige su nombre y pone su PIN. Ve solo lo que le
            corresponde según su rol.
          </DialogDescription>
        </DialogHeader>

        {info.isLoading && <Loader2 className="mx-auto my-8 animate-spin text-muted-foreground" />}
        {info.isError && (
          <Notice tone="error">No se pudo armar el QR. Bloom Equipo necesita el modo red local (es parte de Pro): activalo en Configuración → Red local.</Notice>
        )}
        {info.data && !info.data.url && (
          <Notice>No encontramos la red local de esta PC. Conectala al Wi-Fi del local y volvé a abrir esto.</Notice>
        )}
        {info.data && !info.data.lan_enabled && (
          <Notice>El modo red local está apagado: los celulares no van a poder abrir el link. Activalo en Configuración → Red local.</Notice>
        )}
        {info.data?.network_public && (
          <Notice>Windows tiene esta red como «Pública» y bloquea las conexiones de los celulares. Cambiala a «Privada» (ver la ayuda de Red
              local).</Notice>
        )}

        {info.data?.url && (
          <div className="flex flex-col items-center gap-3">
            <div className="flex size-56 items-center justify-center rounded-2xl border bg-white p-2">
              {qr.data ? (
                <img src={qr.data} alt="Código QR de Bloom Equipo" className="size-full object-contain" />
              ) : (
                <Loader2 className="animate-spin text-muted-foreground" />
              )}
            </div>
            <div className="flex w-full gap-2">
              <Input readOnly value={info.data.url} aria-label="Link de Bloom Equipo" onFocus={(e) => e.currentTarget.select()} />
              <Button variant="outline" size="icon" onClick={copy} aria-label="Copiar link">
                <Copy />
              </Button>
            </div>
            <p className="text-center text-xs text-muted-foreground">
              En el celular: abrí el link y «Agregar a la pantalla principal» para tenerlo como una app.
            </p>
          </div>
        )}

        {info.data && manage && (
          <div className="flex flex-col gap-4 border-t pt-4">
            <div className="flex items-center justify-between gap-3">
              <div className="text-sm">
                <p className="font-medium">Código del QR</p>
                <p className="text-xs text-muted-foreground">Rotarlo corta a quien tenga el link viejo (las sesiones abiertas siguen).</p>
              </div>
              <Button variant="outline" disabled={rotate.isPending} onClick={() => rotate.mutate()}>
                <RefreshCw className={rotate.isPending ? 'animate-spin' : undefined} /> Rotar ahora
              </Button>
            </div>
            <div className="flex items-center justify-between gap-3">
              <label htmlFor="team-rotate" className="text-sm font-medium">
                Rotación
              </label>
              <Select
                value={info.data.rotate}
                onValueChange={(v) => save.mutate({ rotate: v as 'daily' | 'manual' })}
                disabled={save.isPending}
              >
                <SelectTrigger id="team-rotate" className="w-52">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="daily">Una vez por día (recomendado)</SelectItem>
                  <SelectItem value="manual">Solo a mano</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-center justify-between gap-3">
              <label htmlFor="team-lock" className="text-sm font-medium">
                Cerrar sesión del celular tras
              </label>
              <Select
                value={String(info.data.lock_minutes)}
                onValueChange={(v) => save.mutate({ lock_minutes: Number(v) })}
                disabled={save.isPending}
              >
                <SelectTrigger id="team-lock" className="w-52">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {[10, 15, 30, 60, 120, 240].map((m) => (
                    <SelectItem key={m} value={String(m)}>
                      {m < 60 ? `${m} min sin usar` : `${m / 60} h sin usar`}
                    </SelectItem>
                  ))}
                  {![10, 15, 30, 60, 120, 240].includes(info.data.lock_minutes) && (
                    <SelectItem value={String(info.data.lock_minutes)}>{info.data.lock_minutes} min sin usar</SelectItem>
                  )}
                </SelectContent>
              </Select>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
