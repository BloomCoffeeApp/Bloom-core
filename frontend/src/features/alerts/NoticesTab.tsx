import { format } from 'date-fns'
import { Clock, MoreHorizontal, Pencil, Pin, PinOff, Plus, StickyNote, Trash2 } from 'lucide-react'
import { useState } from 'react'

import { ConfirmDialog } from '@/components/confirm-dialog'
import { EmptyState } from '@/components/empty-state'
import { DateTimeField } from '@/components/time-field'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { useAuth } from '@/lib/auth'
import { fmtDateTime, fmtRelative, toDate } from '@/lib/format'
import { cn } from '@/lib/utils'
import { useDepsChanged } from '@/hooks/use-deps-changed'

import { useDeleteNotice, useNotices, useSaveNotice } from './api'
import type { Notice, NoticeColor } from './types'

const NOTICE_COLORS: Record<NoticeColor, { label: string; card: string; swatch: string }> = {
  amber: { label: 'Amarillo', card: 'bg-warning/15 border-warning/40', swatch: 'bg-warning' },
  rose: { label: 'Rojo', card: 'bg-destructive/10 border-destructive/30', swatch: 'bg-destructive' },
  sky: { label: 'Celeste', card: 'bg-info/10 border-info/30', swatch: 'bg-info' },
  emerald: { label: 'Verde', card: 'bg-success/10 border-success/30', swatch: 'bg-success' },
  violet: { label: 'Café', card: 'bg-primary/10 border-primary/30', swatch: 'bg-primary' },
  stone: { label: 'Gris', card: 'bg-muted border-border', swatch: 'bg-muted-foreground' },
}

const TILT = ['-rotate-[0.6deg]', 'rotate-[0.5deg]', 'rotate-0', 'rotate-[0.8deg]', '-rotate-[0.4deg]']

export function NoticesTab() {
  const { can } = useAuth()
  const manager = can('notices.manage')
  const [showExpired, setShowExpired] = useState(false)
  const { data, isLoading } = useNotices(manager && showExpired)
  const [editing, setEditing] = useState<Notice | null>(null)
  const [formOpen, setFormOpen] = useState(false)

  const openNew = () => {
    setEditing(null)
    setFormOpen(true)
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground">Notas para todo el equipo. Las fijadas aparecen primero.</p>
        {manager && (
          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2 text-sm text-muted-foreground">
              <Switch checked={showExpired} onCheckedChange={setShowExpired} /> Ver vencidos
            </label>
            <Button onClick={openNew}>
              <Plus /> Nuevo aviso
            </Button>
          </div>
        )}
      </div>

      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-44 rounded-2xl" />
          ))}
        </div>
      ) : !data?.length ? (
        <EmptyState
          icon={StickyNote}
          title="El tablón está vacío"
          description="Dejá avisos para el equipo: “hoy llega el proveedor de leche”, cambios de turno, promos del día…"
          action={manager ? <Button onClick={openNew}><Plus /> Nuevo aviso</Button> : undefined}
        />
      ) : (
        <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
          {data.map((n, i) => (
            <NoticeCard
              key={n.id}
              notice={n}
              tilt={TILT[i % TILT.length]}
              manager={manager}
              onEdit={() => {
                setEditing(n)
                setFormOpen(true)
              }}
            />
          ))}
        </div>
      )}

      <NoticeFormDialog open={formOpen} onOpenChange={setFormOpen} notice={editing} />
    </div>
  )
}

function NoticeCard({
  notice: n,
  tilt,
  manager,
  onEdit,
}: {
  notice: Notice
  tilt: string
  manager: boolean
  onEdit: () => void
}) {
  const save = useSaveNotice()
  const del = useDeleteNotice()
  const [confirm, setConfirm] = useState(false)
  const color = NOTICE_COLORS[n.color] ?? NOTICE_COLORS.amber

  return (
    <article
      className={cn(
        'relative flex min-h-40 flex-col rounded-2xl border p-5 shadow-sm transition-transform hover:rotate-0',
        color.card,
        tilt,
        n.expired && 'opacity-60',
      )}
    >
      {n.pinned && (
        <span className="absolute -top-2.5 left-1/2 flex size-6 -translate-x-1/2 items-center justify-center rounded-full bg-primary text-primary-foreground shadow">
          <Pin className="size-3.5" />
        </span>
      )}
      <div className="flex items-start justify-between gap-2">
        <h3 className="font-heading text-lg leading-snug font-semibold">{n.title}</h3>
        {manager && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon-sm" className="-mt-1 -mr-2 shrink-0" aria-label="Opciones">
                <MoreHorizontal />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={onEdit}>
                <Pencil /> Editar
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => save.mutate({ id: n.id, data: { pinned: !n.pinned } })}>
                {n.pinned ? <PinOff /> : <Pin />} {n.pinned ? 'Desfijar' : 'Fijar arriba'}
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem variant="destructive" onClick={() => setConfirm(true)}>
                <Trash2 /> Eliminar
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </div>
      {n.body && <p className="mt-2 flex-1 text-sm whitespace-pre-line">{n.body}</p>}
      <div className="mt-4 flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
        <span>
          {n.author_name ?? 'Equipo'} · <span title={fmtDateTime(n.created_at)}>{fmtRelative(n.created_at)}</span>
        </span>
        {n.expires_at && (
          <Badge variant="outline" className={cn('bg-background/60', n.expired && 'text-destructive')}>
            <Clock /> {n.expired ? 'Venció' : 'Vence'} {fmtDateTime(n.expires_at)}
          </Badge>
        )}
      </div>
      <ConfirmDialog
        open={confirm}
        onOpenChange={setConfirm}
        title="¿Eliminar este aviso?"
        description={n.title}
        confirmLabel="Eliminar"
        destructive
        onConfirm={() => del.mutate(n.id)}
      />
    </article>
  )
}

const toLocalInput = (v: string | null) => (v ? format(toDate(v), "yyyy-MM-dd'T'HH:mm") : '')

function NoticeFormDialog({
  open,
  onOpenChange,
  notice,
}: {
  open: boolean
  onOpenChange: (o: boolean) => void
  notice: Notice | null
}) {
  const save = useSaveNotice()
  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')
  const [pinned, setPinned] = useState(false)
  const [color, setColor] = useState<NoticeColor>('amber')
  const [expires, setExpires] = useState('')

  if (useDepsChanged([open, notice]) && open) {
    setTitle(notice?.title ?? '')
    setBody(notice?.body ?? '')
    setPinned(notice?.pinned ?? false)
    setColor(notice?.color ?? 'amber')
    setExpires(toLocalInput(notice?.expires_at ?? null))
  }

  const quickExpire = (hours: number) => {
    const d = new Date()
    if (hours === 0) d.setHours(23, 59, 0, 0)
    else d.setTime(d.getTime() + hours * 3600_000)
    setExpires(format(d, "yyyy-MM-dd'T'HH:mm"))
  }

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!title.trim()) return
    const data = {
      title: title.trim(),
      body: body.trim() || null,
      pinned,
      color,
      expires_at: expires ? new Date(expires).toISOString() : null,
    }
    save.mutate({ id: notice?.id, data }, { onSuccess: () => onOpenChange(false) })
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <form onSubmit={submit} className="grid gap-4">
          <DialogHeader>
            <DialogTitle>{notice ? 'Editar aviso' : 'Nuevo aviso'}</DialogTitle>
            <DialogDescription>Lo va a ver todo el equipo al entrar a Avisos.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-2">
            <Label htmlFor="n-title">Título</Label>
            <Input id="n-title" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Hoy llega el proveedor de leche" autoFocus />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="n-body">Detalle</Label>
            <Textarea id="n-body" value={body} onChange={(e) => setBody(e.target.value)} rows={4} />
          </div>
          <div className="grid gap-2">
            <Label>Color</Label>
            <div className="flex flex-wrap gap-2">
              {(Object.keys(NOTICE_COLORS) as NoticeColor[]).map((c) => (
                <button
                  type="button"
                  key={c}
                  onClick={() => setColor(c)}
                  aria-label={NOTICE_COLORS[c].label}
                  title={NOTICE_COLORS[c].label}
                  className={cn(
                    'size-8 rounded-full ring-offset-2 ring-offset-background transition',
                    NOTICE_COLORS[c].swatch,
                    color === c ? 'ring-2 ring-ring' : 'opacity-70 hover:opacity-100',
                  )}
                />
              ))}
            </div>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="n-exp">Vence (opcional)</Label>
            <div className="flex flex-wrap items-center gap-2">
              <DateTimeField id="n-exp" value={expires} onChange={setExpires} aria-label="Vence" />
              <Button type="button" size="sm" variant="secondary" onClick={() => quickExpire(0)}>
                Hoy
              </Button>
              <Button type="button" size="sm" variant="secondary" onClick={() => quickExpire(24 * 7)}>
                1 semana
              </Button>
              {expires && (
                <Button type="button" size="sm" variant="ghost" onClick={() => setExpires('')}>
                  Sin vencimiento
                </Button>
              )}
            </div>
          </div>
          <label className="flex items-center justify-between rounded-xl border p-3 text-sm">
            <span className="flex items-center gap-2">
              <Pin className="size-4 text-primary" /> Fijar arriba
            </span>
            <Switch checked={pinned} onCheckedChange={setPinned} />
          </label>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancelar
            </Button>
            <Button type="submit" disabled={!title.trim() || save.isPending}>
              {notice ? 'Guardar' : 'Publicar'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
