import {
  ArrowDown,
  ArrowUp,
  Check,
  ClipboardCheck,
  ClipboardList,
  Moon,
  Pencil,
  Plus,
  Settings2,
  Sun,
  Trash2,
  X,
} from 'lucide-react'
import { useEffect, useState } from 'react'

import { EmptyState } from '@/components/empty-state'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Progress } from '@/components/ui/progress'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Switch } from '@/components/ui/switch'
import { useAuth } from '@/lib/auth'
import { fmtTime } from '@/lib/format'
import { cn } from '@/lib/utils'

import { useChecklists, useChecklistsToday, useSaveChecklist, useToggleRunItem } from './api'
import type { Checklist, ChecklistKind, ChecklistRun } from './types'

const KIND: Record<ChecklistKind, { label: string; icon: typeof Sun; tone: string }> = {
  opening: { label: 'Apertura', icon: Sun, tone: 'bg-warning/20 text-warning-foreground dark:text-warning' },
  closing: { label: 'Cierre', icon: Moon, tone: 'bg-info/15 text-info' },
  custom: { label: 'Otro', icon: ClipboardList, tone: 'bg-primary/10 text-primary' },
}

export function ChecklistsTab() {
  const { can } = useAuth()
  const { data, isLoading } = useChecklistsToday()
  const [adminOpen, setAdminOpen] = useState(false)

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground">
          Tildá cada tarea al hacerla: queda registrado quién y a qué hora.
        </p>
        {can('encargado') && (
          <Button variant="outline" onClick={() => setAdminOpen((o) => !o)}>
            <Settings2 /> {adminOpen ? 'Cerrar administración' : 'Administrar checklists'}
          </Button>
        )}
      </div>

      {adminOpen && <ChecklistAdmin />}

      {isLoading ? (
        <div className="grid gap-5 lg:grid-cols-2">
          {Array.from({ length: 2 }).map((_, i) => (
            <Skeleton key={i} className="h-96 rounded-2xl" />
          ))}
        </div>
      ) : !data?.length ? (
        <EmptyState icon={ClipboardList} title="No hay checklists activos" description="Un encargado puede crearlos desde “Administrar checklists”." />
      ) : (
        <div className="grid gap-5 lg:grid-cols-2">
          {data.map((run) => (
            <RunCard key={run.checklist_id} run={run} />
          ))}
        </div>
      )}
    </div>
  )
}

function RunCard({ run }: { run: ChecklistRun }) {
  const toggle = useToggleRunItem()
  const k = KIND[run.kind] ?? KIND.custom
  const pct = run.total ? Math.round((run.done / run.total) * 100) : 0
  const complete = run.total > 0 && run.done === run.total
  const pendingId = toggle.isPending ? toggle.variables?.itemId : undefined

  return (
    <Card className={cn('rounded-2xl transition-colors', complete && 'border-success/40')}>
      <CardHeader className="space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className={cn('flex size-11 items-center justify-center rounded-xl', k.tone)}>
              <k.icon className="size-5" />
            </div>
            <div>
              <CardTitle className="font-heading text-xl">{run.name}</CardTitle>
              <p className="text-xs text-muted-foreground">
                {run.started_at
                  ? `Empezado ${fmtTime(run.started_at)}${run.started_by_name ? ` por ${run.started_by_name}` : ''}`
                  : 'Todavía no se empezó hoy'}
              </p>
            </div>
          </div>
          {complete ? (
            <Badge className="bg-success text-success-foreground">
              <Check /> Completo {run.completed_at && fmtTime(run.completed_at)}
            </Badge>
          ) : (
            <span className="tabular text-sm font-medium text-muted-foreground">
              {run.done}/{run.total}
            </span>
          )}
        </div>
        <Progress value={pct} className={cn('h-2', complete && '[&>*]:bg-success')} />
      </CardHeader>
      <CardContent>
        <ul className="space-y-2">
          {run.items.map((it) => (
            <li key={it.item_id}>
              <button
                type="button"
                disabled={pendingId === it.item_id}
                onClick={() => toggle.mutate({ run, itemId: it.item_id, done: !it.done })}
                aria-pressed={it.done}
                className={cn(
                  'touch-target flex w-full items-center gap-4 rounded-xl border px-4 py-3 text-left transition-colors',
                  'hover:bg-muted/60 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none',
                  it.done && 'border-success/30 bg-success/10 hover:bg-success/15',
                  pendingId === it.item_id && 'opacity-60',
                )}
              >
                <span
                  className={cn(
                    'flex size-8 shrink-0 items-center justify-center rounded-lg border-2 transition-colors',
                    it.done ? 'border-success bg-success text-success-foreground' : 'border-input bg-background',
                  )}
                >
                  {it.done && <Check className="size-5" strokeWidth={3} />}
                </span>
                <span className="min-w-0 flex-1">
                  <span className={cn('block text-base', it.done && 'text-muted-foreground line-through')}>{it.text}</span>
                  {it.done && (it.done_by_name || it.done_at) && (
                    <span className="block text-xs text-muted-foreground">
                      {it.done_by_name ?? 'Alguien'} · {fmtTime(it.done_at)}
                    </span>
                  )}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  )
}

// ---------------------------------------------------------------- admin

function ChecklistAdmin() {
  const { data, isLoading } = useChecklists()
  const save = useSaveChecklist()
  const [editing, setEditing] = useState<Checklist | null>(null)
  const [open, setOpen] = useState(false)

  return (
    <Card className="rounded-2xl border-dashed">
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="flex items-center gap-2">
          <ClipboardCheck className="size-4 text-primary" /> Administrar checklists
        </CardTitle>
        <Button
          size="sm"
          onClick={() => {
            setEditing(null)
            setOpen(true)
          }}
        >
          <Plus /> Nuevo checklist
        </Button>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <Skeleton className="h-24 w-full" />
        ) : (
          <ul className="divide-y">
            {data?.map((c) => {
              const k = KIND[c.kind] ?? KIND.custom
              return (
                <li key={c.id} className="flex items-center gap-3 py-3">
                  <div className={cn('flex size-9 items-center justify-center rounded-lg', k.tone)}>
                    <k.icon className="size-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className={cn('font-medium', !c.active && 'text-muted-foreground')}>{c.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {k.label} · {c.items.length} tareas{!c.active && ' · desactivado'}
                    </p>
                  </div>
                  <Switch
                    checked={c.active}
                    onCheckedChange={(active) => save.mutate({ id: c.id, data: { active } })}
                    aria-label="Activo"
                  />
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label="Editar"
                    onClick={() => {
                      setEditing(c)
                      setOpen(true)
                    }}
                  >
                    <Pencil />
                  </Button>
                </li>
              )
            })}
          </ul>
        )}
      </CardContent>
      <ChecklistFormDialog open={open} onOpenChange={setOpen} checklist={editing} />
    </Card>
  )
}

type DraftItem = { key: string; id?: number; text: string }
let draftSeq = 0
const newKey = () => `n${++draftSeq}`

function ChecklistFormDialog({
  open,
  onOpenChange,
  checklist,
}: {
  open: boolean
  onOpenChange: (o: boolean) => void
  checklist: Checklist | null
}) {
  const save = useSaveChecklist()
  const [name, setName] = useState('')
  const [kind, setKind] = useState<ChecklistKind>('custom')
  const [items, setItems] = useState<DraftItem[]>([])
  const [newText, setNewText] = useState('')

  useEffect(() => {
    if (!open) return
    setName(checklist?.name ?? '')
    setKind(checklist?.kind ?? 'custom')
    setItems(checklist?.items.map((i) => ({ key: `i${i.id}`, id: i.id, text: i.text })) ?? [])
    setNewText('')
  }, [open, checklist])

  const add = () => {
    if (!newText.trim()) return
    setItems((xs) => [...xs, { key: newKey(), text: newText.trim() }])
    setNewText('')
  }
  const move = (i: number, d: -1 | 1) =>
    setItems((xs) => {
      const j = i + d
      if (j < 0 || j >= xs.length) return xs
      const copy = [...xs]
      ;[copy[i], copy[j]] = [copy[j], copy[i]]
      return copy
    })

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    const clean = items.filter((i) => i.text.trim()).map((i) => ({ id: i.id, text: i.text.trim() }))
    if (newText.trim()) clean.push({ id: undefined, text: newText.trim() })
    save.mutate(
      { id: checklist?.id, data: { name: name.trim(), kind, items: clean } },
      { onSuccess: () => onOpenChange(false) },
    )
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <form onSubmit={submit} className="grid gap-4">
          <DialogHeader>
            <DialogTitle>{checklist ? 'Editar checklist' : 'Nuevo checklist'}</DialogTitle>
            <DialogDescription>Las tareas se tildan una vez por día.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 sm:grid-cols-[1fr_10rem]">
            <div className="grid gap-2">
              <Label htmlFor="cl-name">Nombre</Label>
              <Input id="cl-name" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
            </div>
            <div className="grid gap-2">
              <Label>Tipo</Label>
              <Select value={kind} onValueChange={(v) => setKind(v as ChecklistKind)}>
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {(Object.keys(KIND) as ChecklistKind[]).map((k) => (
                    <SelectItem key={k} value={k}>
                      {KIND[k].label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="grid gap-2">
            <Label>Tareas</Label>
            <ul className="max-h-72 space-y-1.5 overflow-y-auto">
              {items.map((it, i) => (
                <li key={it.key} className="flex items-center gap-1.5">
                  <span className="tabular w-5 text-right text-xs text-muted-foreground">{i + 1}</span>
                  <Input
                    value={it.text}
                    onChange={(e) =>
                      setItems((xs) => xs.map((x) => (x.key === it.key ? { ...x, text: e.target.value } : x)))
                    }
                  />
                  <Button type="button" variant="ghost" size="icon-sm" onClick={() => move(i, -1)} disabled={i === 0} aria-label="Subir">
                    <ArrowUp />
                  </Button>
                  <Button type="button" variant="ghost" size="icon-sm" onClick={() => move(i, 1)} disabled={i === items.length - 1} aria-label="Bajar">
                    <ArrowDown />
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    className="text-destructive"
                    onClick={() => setItems((xs) => xs.filter((x) => x.key !== it.key))}
                    aria-label="Quitar"
                  >
                    {it.id ? <Trash2 /> : <X />}
                  </Button>
                </li>
              ))}
            </ul>
            <div className="flex gap-2">
              <Input
                value={newText}
                onChange={(e) => setNewText(e.target.value)}
                placeholder="Agregá una tarea y apretá Enter"
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault()
                    add()
                  }
                }}
              />
              <Button type="button" variant="secondary" onClick={add} disabled={!newText.trim()}>
                <Plus /> Agregar
              </Button>
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancelar
            </Button>
            <Button type="submit" disabled={!name.trim() || save.isPending}>
              Guardar
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
