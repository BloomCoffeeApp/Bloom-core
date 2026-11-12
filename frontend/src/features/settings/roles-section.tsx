import { Loader2, Plus, RotateCcw, ShieldCheck, Trash2 } from 'lucide-react'
import { useMemo, useState } from 'react'
import { toast } from 'sonner'

import { ConfirmDialog } from '@/components/confirm-dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import type { Permission } from '@/lib/permissions'
import { cn } from '@/lib/utils'

import { useDeleteRole, usePermissionCatalog, useResetRole, useRoles, useSaveRole } from './api'
import { CardSkeleton, Field, SettingsCard } from './form'
import type { PermissionInfo, RoleRow } from './types'

/** Adds what each permission requires (same rule as the backend's `normalize`). */
function withRequirements(perms: Set<Permission>, catalog: PermissionInfo[]): Set<Permission> {
  const out = new Set(perms)
  for (const p of catalog) if (out.has(p.key) && p.requires) out.add(p.requires)
  return out
}

function RoleEditor({ role, catalog, onDone }: { role: RoleRow | null; catalog: PermissionInfo[]; onDone: (key?: string) => void }) {
  const [name, setName] = useState(role?.name ?? '')
  const [perms, setPerms] = useState<Set<Permission>>(() => new Set(role?.permissions ?? ['pos.sell']))
  const [confirmDelete, setConfirmDelete] = useState(false)
  const save = useSaveRole()
  const reset = useResetRole()
  const del = useDeleteRole()
  const readOnly = role !== null && !role.editable
  const groups = useMemo(() => {
    const m = new Map<string, PermissionInfo[]>()
    for (const p of catalog) m.set(p.group, [...(m.get(p.group) ?? []), p])
    return [...m.entries()]
  }, [catalog])
  const requiredBy = (key: Permission) => catalog.filter((p) => p.requires === key && perms.has(p.key)).map((p) => p.label)

  const toggle = (p: PermissionInfo, on: boolean) => {
    const next = new Set(perms)
    if (on) next.add(p.key)
    else {
      next.delete(p.key)
      for (const q of catalog) if (q.requires === p.key) next.delete(q.key)
    }
    setPerms(withRequirements(next, catalog))
  }

  const submit = () =>
    save.mutate(
      { key: role?.key, data: { name: name.trim(), permissions: [...perms] } },
      {
        onSuccess: (r) => {
          toast.success(role ? `Rol «${r.name}» actualizado` : `Rol «${r.name}» creado`)
          onDone(r.key)
        },
      },
    )

  return (
    <SettingsCard
      title={role ? role.name : 'Nuevo rol'}
      description={
        readOnly
          ? 'El administrador siempre tiene acceso total y no se puede editar: así nunca quedás afuera de tu propio sistema.'
          : 'Marcá lo que puede hacer. Los cambios valen desde la próxima acción de cada usuario con este rol.'
      }
      action={
        role && !readOnly ? (
          <div className="flex gap-2">
            {role.builtin && role.customized && (
              <Button variant="outline" size="sm" className="h-11" onClick={() => reset.mutate(role.key, { onSuccess: (r) => (setPerms(new Set(r.permissions)), toast.success('Rol restablecido')) })}>
                <RotateCcw /> Restablecer
              </Button>
            )}
            {!role.builtin && (
              <Button variant="outline" size="sm" className="h-11" onClick={() => setConfirmDelete(true)}>
                <Trash2 /> Borrar
              </Button>
            )}
          </div>
        ) : undefined
      }
      footer={
        readOnly ? undefined : (
          <div className="flex justify-end gap-2">
            {!role && (
              <Button variant="outline" className="h-11" onClick={() => onDone()}>
                Cancelar
              </Button>
            )}
            <Button className="h-11" disabled={!name.trim() || save.isPending} onClick={submit} data-testid="role-save">
              {save.isPending && <Loader2 className="animate-spin" />} Guardar rol
            </Button>
          </div>
        )
      }
    >
      <div className="space-y-5">
        {!readOnly && (
          <Field label="Nombre del rol" htmlFor="role-name">
            <Input id="role-name" className="h-11" value={name} maxLength={40} onChange={(e) => setName(e.target.value)} placeholder="Ej.: Mozo, Cajero de la tarde" />
          </Field>
        )}
        {groups.map(([group, items]) => (
          <fieldset key={group} className="space-y-2">
            <legend className="mb-1 text-xs font-semibold tracking-wide text-muted-foreground uppercase">{group}</legend>
            <div className="grid gap-2 sm:grid-cols-2">
              {items.map((p) => {
                const on = readOnly || perms.has(p.key)
                const lockedBy = readOnly ? [] : requiredBy(p.key)
                return (
                  <label
                    key={p.key}
                    className={cn(
                      'flex min-h-14 cursor-pointer items-start gap-3 rounded-xl border p-3 transition',
                      on ? 'border-primary/40 bg-primary/5' : 'hover:bg-muted/50',
                      readOnly && 'cursor-default',
                    )}
                  >
                    <Checkbox
                      className="mt-0.5 size-5"
                      checked={on}
                      disabled={readOnly || lockedBy.length > 0}
                      onCheckedChange={(v) => toggle(p, v === true)}
                      aria-label={p.label}
                    />
                    <span className="grid gap-0.5 leading-tight">
                      <span className="text-sm font-medium">{p.label}</span>
                      <span className="text-xs text-muted-foreground">
                        {p.description}
                        {lockedBy.length > 0 && ` · Lo necesita «${lockedBy.join('», «')}»`}
                      </span>
                    </span>
                  </label>
                )
              })}
            </div>
          </fieldset>
        ))}
      </div>
      {role && (
        <ConfirmDialog
          open={confirmDelete}
          onOpenChange={setConfirmDelete}
          title={`¿Borrar el rol «${role.name}»?`}
          description={role.users ? `Lo usan ${role.users} usuario(s): primero cambiales el rol.` : 'No lo usa nadie. Queda registrado en la auditoría.'}
          confirmLabel="Borrar"
          destructive
          onConfirm={() => del.mutate(role.key, { onSuccess: () => (toast.success('Rol borrado'), onDone()) })}
        />
      )}
    </SettingsCard>
  )
}

/** Configuración → Roles y permisos (admin only). */
export function RolesSection() {
  const roles = useRoles()
  const catalog = usePermissionCatalog()
  const [selected, setSelected] = useState<string | 'new'>('encargado')
  if (!roles.data || !catalog.data) return <CardSkeleton />
  const role = selected === 'new' ? null : (roles.data.find((r) => r.key === selected) ?? roles.data[0])
  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(220px,280px)_1fr]">
      <div className="space-y-2" role="listbox" aria-label="Roles">
        {roles.data.map((r) => (
          <button
            key={r.key}
            role="option"
            aria-selected={role?.key === r.key}
            onClick={() => setSelected(r.key)}
            className={cn(
              'flex min-h-14 w-full items-center gap-3 rounded-xl border p-3 text-left transition',
              role?.key === r.key ? 'border-primary bg-primary/5' : 'hover:bg-muted/50',
            )}
          >
            <ShieldCheck className={cn('size-5 shrink-0', r.key === 'admin' ? 'text-primary' : 'text-muted-foreground')} />
            <span className="grid flex-1 gap-0.5 leading-tight">
              <span className="text-sm font-medium">{r.name}</span>
              <span className="text-xs text-muted-foreground">
                {r.key === 'admin' ? 'Acceso total' : `${r.permissions.length} permisos`} · {r.users} usuario{r.users === 1 ? '' : 's'}
              </span>
            </span>
            {!r.builtin && <Badge variant="outline">Propio</Badge>}
            {r.customized && <Badge variant="secondary">Editado</Badge>}
          </button>
        ))}
        <Button variant="outline" className="h-12 w-full" onClick={() => setSelected('new')}>
          <Plus /> Nuevo rol
        </Button>
      </div>
      <RoleEditor
        key={selected === 'new' ? 'new' : role?.key}
        role={role}
        catalog={catalog.data}
        onDone={(key) => setSelected(key ?? 'encargado')}
      />
    </div>
  )
}
