import { KeyRound, Loader2, Pencil, Plus, ShieldCheck, Smartphone, UserPlus } from 'lucide-react'
import { useMemo, useState } from 'react'
import { toast } from 'sonner'

import { AVATAR_COLORS, initials } from '@/components/avatar-utils'
import { type ColumnDef, DataTable } from '@/components/data-table'
import { LockBadge } from '@/components/lock-badge'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { type Role, useAuth } from '@/lib/auth'
import { fmtRelative, ROLE_LABEL } from '@/lib/format'
import { cn } from '@/lib/utils'

import { useCreateUser, useRoles, useUpdateUser, useUsers } from './api'
import { Field, SettingsCard } from './form'
import type { UserRow } from './types'
import { SessionsDialog } from '../team/sessions-dialog'
import { UserPermissionsDialog } from './user-permissions-dialog'

const COLORS = Object.keys(AVATAR_COLORS)
const PIN_RE = /^\d{4,6}$/

function UserAvatar({ name, color, className }: { name: string; color: string; className?: string }) {
  return (
    <Avatar className={cn('size-9', className)}>
      <AvatarFallback className={cn('text-xs font-semibold', AVATAR_COLORS[color] ?? AVATAR_COLORS.amber)}>{initials(name)}</AvatarFallback>
    </Avatar>
  )
}

type DialogState =
  | { mode: 'create' }
  | { mode: 'edit'; user: UserRow }
  | { mode: 'pin'; user: UserRow }
  | { mode: 'permissions'; user: UserRow }
  | { mode: 'sessions'; user: UserRow }
  | null

function UserDialog({ state, onClose }: { state: Exclude<DialogState, { mode: 'permissions' } | null>; onClose: () => void }) {
  const editing = state.mode !== 'create' ? state.user : null
  const [name, setName] = useState(editing?.name ?? '')
  const [role, setRole] = useState<Role>(editing?.role ?? 'cajero')
  const [color, setColor] = useState(editing?.color ?? 'amber')
  const roles = useRoles()
  const { can, user: me } = useAuth()
  const current = roles.data?.find((r) => r.key === role)
  const mine = new Set(me?.permissions ?? [])
  // Non-admins with "Usuarios" can only hand out roles that don't exceed their own permissions.
  const assignable = (roles.data ?? []).filter(
    (r) => can() || (r.key !== 'admin' && r.permissions.every((p) => mine.has(p))),
  )
  const [pin, setPin] = useState('')
  const [pin2, setPin2] = useState('')
  const create = useCreateUser()
  const update = useUpdateUser()
  const busy = create.isPending || update.isPending
  const needsPin = state.mode !== 'edit'
  const pinOk = PIN_RE.test(pin) && pin === pin2
  const valid = state.mode === 'pin' ? pinOk : !!name.trim() && (!needsPin || pinOk)

  const submit = () => {
    if (!valid) return
    if (state.mode === 'create') {
      create.mutate({ name: name.trim(), role, color, pin }, { onSuccess: onClose })
    } else if (state.mode === 'edit') {
      update.mutate(
        { id: state.user.id, data: { name: name.trim(), role, color } },
        { onSuccess: () => (toast.success('Usuario actualizado'), onClose()) },
      )
    } else {
      update.mutate({ id: state.user.id, data: { pin } }, { onSuccess: () => (toast.success(`PIN de ${state.user.name} actualizado`), onClose()) })
    }
  }

  const title = state.mode === 'create' ? 'Nuevo usuario' : state.mode === 'edit' ? 'Editar usuario' : 'Restablecer PIN'
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>
            {state.mode === 'pin' ? `Ingresá el nuevo PIN para ${state.user.name}.` : 'Cada persona entra con su nombre y un PIN de 4 a 6 dígitos.'}
          </DialogDescription>
        </DialogHeader>
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault()
            submit()
          }}
        >
          {state.mode !== 'pin' && (
            <>
              <div className="flex items-center gap-3">
                <UserAvatar name={name || '?'} color={color} className="size-12 text-base" />
                <Field label="Nombre" htmlFor="u-name" className="flex-1">
                  <Input id="u-name" value={name} onChange={(e) => setName(e.target.value)} maxLength={80} autoFocus placeholder="Ej.: Caja mañana" />
                </Field>
              </div>
              <Field
                label="Rol"
                hint={current?.hint ?? (current ? `${current.permissions.length} permisos · se editan en «Roles y permisos»` : undefined)}
              >
                <Select value={role} onValueChange={(v) => setRole(v as Role)}>
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {assignable.map((r) => (
                      <SelectItem key={r.key} value={r.key}>
                        {r.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>
              <Field label="Color del avatar">
                <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Color">
                  {COLORS.map((c) => (
                    <button
                      key={c}
                      type="button"
                      role="radio"
                      aria-checked={color === c}
                      aria-label={c}
                      onClick={() => setColor(c)}
                      className={cn(
                        'flex size-9 items-center justify-center rounded-full text-xs font-semibold transition-[transform,box-shadow,border-color,background-color,color] motion-fast',
                        AVATAR_COLORS[c],
                        color === c ? 'ring-2 ring-primary ring-offset-2 ring-offset-background' : 'opacity-70 hover:opacity-100',
                      )}
                    >
                      {initials(name || 'A')}
                    </button>
                  ))}
                </div>
              </Field>
            </>
          )}
          {needsPin && (
            <div className="grid grid-cols-2 gap-3">
              <Field label="PIN" htmlFor="u-pin" hint="4 a 6 dígitos">
                <Input
                  id="u-pin"
                  type="password"
                  inputMode="numeric"
                  autoComplete="new-password"
                  value={pin}
                  maxLength={6}
                  onChange={(e) => setPin(e.target.value.replace(/\D/g, ''))}
                  autoFocus={state.mode === 'pin'}
                />
              </Field>
              <Field label="Repetí el PIN" htmlFor="u-pin2">
                <Input
                  id="u-pin2"
                  type="password"
                  inputMode="numeric"
                  autoComplete="new-password"
                  value={pin2}
                  maxLength={6}
                  onChange={(e) => setPin2(e.target.value.replace(/\D/g, ''))}
                  aria-invalid={!!pin2 && pin !== pin2}
                />
              </Field>
              {!!pin2 && pin !== pin2 && <p className="col-span-2 text-xs text-destructive">Los PIN no coinciden.</p>}
            </div>
          )}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              Cancelar
            </Button>
            <Button type="submit" disabled={!valid || busy}>
              {busy && <Loader2 className="animate-spin" />}
              {state.mode === 'create' ? 'Crear usuario' : 'Guardar'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export function UsersSection() {
  const { user: me } = useAuth()
  const users = useUsers(true)
  const update = useUpdateUser()
  const [dialog, setDialog] = useState<DialogState>(null)

  const columns = useMemo<ColumnDef<UserRow, unknown>[]>(
    () => [
      {
        accessorKey: 'name',
        header: 'Usuario',
        cell: ({ row }) => (
          <div className={cn('flex items-center gap-3', !row.original.active && 'opacity-50')}>
            <UserAvatar name={row.original.name} color={row.original.color} />
            <div>
              <p className="font-medium">
                {row.original.name}
                {row.original.id === me?.id && <span className="ml-1.5 text-xs text-muted-foreground">(vos)</span>}
                {row.original.locked && <LockBadge className="ml-1.5" />}
              </p>
              <p className="text-xs text-muted-foreground">
                {row.original.last_login_at ? `Último ingreso ${fmtRelative(row.original.last_login_at)}` : 'Nunca ingresó'}
              </p>
            </div>
          </div>
        ),
      },
      {
        accessorKey: 'role',
        header: 'Rol',
        cell: ({ row }) => {
          const r = row.original.role
          const extra = (row.original.perm_grants?.length ?? 0) + (row.original.perm_revokes?.length ?? 0)
          return (
            <div className="flex flex-wrap items-center gap-1.5">
              <Badge variant={r === 'admin' ? 'default' : 'secondary'}>{row.original.role_name ?? ROLE_LABEL[r] ?? r}</Badge>
              {extra > 0 && <Badge variant="outline">{extra} excepci{extra === 1 ? 'ón' : 'ones'}</Badge>}
            </div>
          )
        },
      },
      {
        accessorKey: 'active',
        header: 'Activo',
        cell: ({ row }) => (
          <Switch
            checked={row.original.active}
            disabled={row.original.id === me?.id || update.isPending}
            aria-label={row.original.active ? 'Desactivar' : 'Activar'}
            onCheckedChange={(v) =>
              update.mutate(
                { id: row.original.id, data: { active: v } },
                { onSuccess: () => toast.success(v ? `${row.original.name} activado` : `${row.original.name} desactivado`) },
              )
            }
          />
        ),
      },
      {
        id: 'actions',
        header: '',
        enableSorting: false,
        cell: ({ row }) => (
          <div className="flex justify-end gap-1">
            <Button variant="ghost" size="sm" onClick={() => setDialog({ mode: 'sessions', user: row.original })}>
              <Smartphone /> Sesiones
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setDialog({ mode: 'pin', user: row.original })}>
              <KeyRound /> PIN
            </Button>
            {row.original.role !== 'admin' && (
              <Button variant="ghost" size="sm" onClick={() => setDialog({ mode: 'permissions', user: row.original })}>
                <ShieldCheck /> Permisos
              </Button>
            )}
            <Button variant="ghost" size="sm" onClick={() => setDialog({ mode: 'edit', user: row.original })}>
              <Pencil /> Editar
            </Button>
          </div>
        ),
      },
    ],
    [me?.id, update],
  )

  return (
    <SettingsCard
      title="Usuarios"
      description="Quién usa la app y qué puede hacer cada uno."
      action={
        <Button onClick={() => setDialog({ mode: 'create' })}>
          <Plus /> Nuevo usuario
        </Button>
      }
    >
      <DataTable
        columns={columns}
        data={users.data}
        loading={users.isLoading}
        searchPlaceholder="Buscar usuario…"
        emptyTitle="No hay usuarios"
        toolbar={
          users.data && (
            <span className="text-sm text-muted-foreground">
              <UserPlus className="mr-1 inline size-4" />
              {users.data.filter((u) => u.active).length} activos de {users.data.length}
            </span>
          )
        }
      />
      {dialog?.mode === 'permissions' && <UserPermissionsDialog key={dialog.user.id} user={dialog.user} onClose={() => setDialog(null)} />}
      {dialog?.mode === 'sessions' && <SessionsDialog key={dialog.user.id} user={dialog.user} onClose={() => setDialog(null)} />}
      {dialog && dialog.mode !== 'permissions' && dialog.mode !== 'sessions' && (
        <UserDialog key={dialog.mode + ('user' in dialog ? dialog.user.id : '')} state={dialog} onClose={() => setDialog(null)} />
      )}
    </SettingsCard>
  )
}
