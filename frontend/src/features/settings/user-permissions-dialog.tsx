import { Loader2 } from 'lucide-react'
import { useMemo, useState } from 'react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { useAuth } from '@/lib/auth'
import type { Permission } from '@/lib/permissions'
import { cn } from '@/lib/utils'

import { usePermissionCatalog, useRoles, useSetUserPermissions } from './api'
import type { PermissionInfo, UserRow } from './types'

/** Same rule as the backend's `apply_overrides`: role + grants (with what they require) - revokes, then drop
 *  whatever lost its requirement. */
function effective(base: Set<Permission>, grants: Set<Permission>, revokes: Set<Permission>, catalog: PermissionInfo[]) {
  const out = new Set<Permission>([...base, ...grants])
  for (const p of catalog) if (out.has(p.key) && p.requires) out.add(p.requires)
  for (const r of revokes) out.delete(r)
  let changed = true
  while (changed) {
    changed = false
    for (const p of catalog) {
      if (out.has(p.key) && p.requires && !out.has(p.requires)) {
        out.delete(p.key)
        changed = true
      }
    }
  }
  return out
}

/** Configuración → Usuarios → «Permisos de esta persona»: the role is the base, here only the exceptions. */
export function UserPermissionsDialog({ user, onClose }: { user: UserRow; onClose: () => void }) {
  const roles = useRoles()
  const catalog = usePermissionCatalog()
  const { can, user: me } = useAuth()
  const save = useSetUserPermissions()
  const role = roles.data?.find((r) => r.key === user.role)
  const base = useMemo(() => new Set<Permission>(role?.permissions ?? []), [role])
  const [grants, setGrants] = useState<Set<Permission>>(() => new Set(user.perm_grants ?? []))
  const [revokes, setRevokes] = useState<Set<Permission>>(() => new Set(user.perm_revokes ?? []))
  const mine = new Set(me?.permissions ?? [])
  const cat = useMemo(() => catalog.data ?? [], [catalog.data])
  const eff = useMemo(() => effective(base, grants, revokes, cat), [base, grants, revokes, cat])
  const groups = useMemo(() => {
    const m = new Map<string, PermissionInfo[]>()
    for (const p of cat) m.set(p.group, [...(m.get(p.group) ?? []), p])
    return [...m.entries()]
  }, [cat])
  const label = (key: Permission) => cat.find((p) => p.key === key)?.label ?? key
  const isAdmin = user.role === 'admin'

  const toggle = (p: PermissionInfo, on: boolean) => {
    const g = new Set(grants)
    const r = new Set(revokes)
    if (on) {
      // Turning on: lift the revoke (or add a grant) and, if the requirement was revoked, lift that too.
      r.delete(p.key)
      if (!base.has(p.key)) g.add(p.key)
      let req: Permission | null = p.requires
      while (req) {
        r.delete(req)
        if (!base.has(req)) g.add(req)
        const current: Permission = req
        req = cat.find((q) => q.key === current)?.requires ?? null
      }
    } else {
      g.delete(p.key)
      if (base.has(p.key)) r.add(p.key)
    }
    setGrants(g)
    setRevokes(r)
  }

  // What actually changes after the server drops redundant entries.
  const added = [...eff].filter((k) => !base.has(k))
  const removed = [...base].filter((k) => !eff.has(k))
  const hadExceptions = (user.perm_grants?.length ?? 0) + (user.perm_revokes?.length ?? 0) > 0
  const dirty = added.length + removed.length > 0 || hadExceptions

  const submit = () =>
    save.mutate(
      { id: user.id, grants: [...grants], revokes: [...revokes] },
      { onSuccess: () => (toast.success(`Permisos de ${user.name} actualizados`), onClose()) },
    )

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>Permisos de {user.name}</DialogTitle>
          <DialogDescription>
            {isAdmin
              ? 'El administrador siempre tiene acceso total: no admite excepciones.'
              : `Parte del rol ${role?.name ?? user.role_name ?? user.role}. Lo gris viene del rol; lo que cambies acá vale solo para esta persona.`}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-5" data-testid="user-permissions">
          {groups.map(([group, items]) => (
            <fieldset key={group} className="space-y-2">
              <legend className="mb-1 text-xs font-semibold tracking-wide text-muted-foreground uppercase">{group}</legend>
              <div className="grid gap-2 sm:grid-cols-2">
                {items.map((p) => {
                  const on = isAdmin || eff.has(p.key)
                  const fromRole = base.has(p.key)
                  const state = on ? (fromRole ? 'role' : 'granted') : fromRole ? 'revoked' : 'off'
                  const missingReq = !on && !!p.requires && !eff.has(p.requires) && !revokes.has(p.key) && (grants.has(p.key) || fromRole)
                  // A non-admin can only hand out what they have themselves.
                  const cannotGrant = !can() && !on && !mine.has(p.key)
                  return (
                    <label
                      key={p.key}
                      className={cn(
                        'flex min-h-14 cursor-pointer items-start gap-3 rounded-xl border p-3 transition',
                        state === 'granted' && 'border-primary/50 bg-primary/5',
                        state === 'revoked' && 'border-destructive/40 bg-destructive/5',
                        state === 'role' && 'bg-muted/40',
                        (isAdmin || cannotGrant) && 'cursor-default opacity-70',
                      )}
                    >
                      <Checkbox
                        className="mt-0.5 size-5"
                        checked={on}
                        disabled={isAdmin || cannotGrant}
                        onCheckedChange={(v) => toggle(p, v === true)}
                        aria-label={p.label}
                      />
                      <span className="grid flex-1 gap-0.5 leading-tight">
                        <span className="flex flex-wrap items-center gap-1.5 text-sm font-medium">
                          {p.label}
                          {state === 'role' && <span className="text-xs font-normal text-muted-foreground">del rol</span>}
                          {state === 'granted' && <Badge variant="default">Agregado</Badge>}
                          {state === 'revoked' && <Badge variant="destructive">Quitado</Badge>}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {p.description}
                          {missingReq && p.requires && ` · Necesita «${label(p.requires)}»`}
                          {cannotGrant && ' · No podés dar un permiso que vos no tenés'}
                        </span>
                      </span>
                    </label>
                  )
                })}
              </div>
            </fieldset>
          ))}
        </div>
        <DialogFooter className="items-center sm:justify-between">
          <span className="text-xs text-muted-foreground">
            {added.length + removed.length === 0
              ? 'Sin excepciones: tiene exactamente lo del rol.'
              : `${added.length} agregado${added.length === 1 ? '' : 's'} · ${removed.length} quitado${removed.length === 1 ? '' : 's'} respecto del rol`}
          </span>
          <div className="flex gap-2">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancelar
            </Button>
            {!isAdmin && (
              <Button type="button" onClick={submit} disabled={!dirty || save.isPending} data-testid="user-permissions-save">
                {save.isPending && <Loader2 className="animate-spin" />} Guardar permisos
              </Button>
            )}
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
