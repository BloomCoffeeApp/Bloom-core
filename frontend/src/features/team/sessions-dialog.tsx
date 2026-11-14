import { Loader2, Smartphone, Monitor } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { fmtRelative } from '@/lib/format'

import { deviceLabel, useDisconnectSession, useUserSessions } from './api'

/** Configuración → Usuarios → «Sesiones»: where this person is logged in (the register, a phone with Bloom Equipo…)
 *  and a button to disconnect one of them. */
export function SessionsDialog({ user, onClose }: { user: { id: number; name: string }; onClose: () => void }) {
  const sessions = useUserSessions(user.id)
  const disconnect = useDisconnectSession(user.id)
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Sesiones abiertas de {user.name}</DialogTitle>
          <DialogDescription>
            Si perdió el celular o dejó la sesión abierta en otro equipo, desconectala desde acá: ese equipo vuelve a pedir el PIN.
          </DialogDescription>
        </DialogHeader>
        {sessions.isLoading && <Loader2 className="mx-auto my-6 animate-spin text-muted-foreground" />}
        {sessions.data?.length === 0 && <p className="py-6 text-center text-sm text-muted-foreground">No tiene sesiones abiertas.</p>}
        <ul className="flex flex-col gap-2">
          {sessions.data?.map((s) => {
            const phone = s.client === 'equipo'
            const Icon = phone ? Smartphone : Monitor
            return (
              <li key={s.id} className="flex items-center gap-3 rounded-xl border p-3">
                <Icon className="size-5 shrink-0 text-muted-foreground" aria-hidden />
                <div className="min-w-0 flex-1 text-sm">
                  <p className="flex flex-wrap items-center gap-1.5 font-medium">
                    {phone ? 'Bloom Equipo' : 'Bloom'}
                    <span className="font-normal text-muted-foreground">· {deviceLabel(s.user_agent)}</span>
                    {s.current && <Badge variant="secondary">esta sesión</Badge>}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Última actividad {s.last_seen_at ? fmtRelative(s.last_seen_at) : '—'} · abierta {fmtRelative(s.created_at)}
                  </p>
                </div>
                <Button variant="outline" size="sm" disabled={disconnect.isPending} onClick={() => disconnect.mutate(s.id)}>
                  Desconectar
                </Button>
              </li>
            )
          })}
        </ul>
      </DialogContent>
    </Dialog>
  )
}
