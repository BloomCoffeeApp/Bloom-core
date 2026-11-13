import { Gift, Laptop, Moon, Sun } from 'lucide-react'
import { useState } from 'react'

import { type ColumnDef, DataTable } from '@/components/data-table'
import { MoneyInput } from '@/components/money-input'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { fmtDateTime, fmtMoney, fmtNumber, formatCuit } from '@/lib/format'
import { type Theme, useTheme } from '@/lib/theme'
import { cn } from '@/lib/utils'

import { useAudit, useSaveSetting } from './api'
import { Field, NumberInput, SettingsCard, SwitchRow } from './form'
import { validNumbers } from './validation'
import type { AlertsSettings, AuditRow, BusinessSettings, LoyaltySettings } from './types'

const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b)

export function BusinessSection({ initial }: { initial: BusinessSettings }) {
  const [f, setF] = useState(initial)
  const save = useSaveSetting('business', 'Datos del negocio guardados')
  const set = (k: keyof BusinessSettings) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value })
  return (
    <SettingsCard
      title="Datos del negocio"
      description="Aparecen en los tickets y en los reportes."
      onSave={() => save.mutate({ ...f, name: f.name.trim() })}
      saving={save.isPending}
      dirty={!same(f, initial) && !!f.name.trim()}
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Nombre del negocio" htmlFor="biz-name">
          <Input id="biz-name" value={f.name} onChange={set('name')} placeholder="Mi Cafetería" />
        </Field>
        <Field label="Razón social" htmlFor="biz-legal" hint="Opcional. Como figura en tu inscripción; aparece en el comprobante.">
          <Input id="biz-legal" value={f.legal_name ?? ''} onChange={set('legal_name')} placeholder="Mi Cafetería S.R.L. / Nombre y apellido" />
        </Field>
        <Field label="CUIT" htmlFor="biz-cuit" hint="Formato 20-12345678-9">
          <Input
            id="biz-cuit"
            value={f.cuit}
            onChange={(e) => setF({ ...f, cuit: formatCuit(e.target.value) })}
            placeholder="00-00000000-0"
            inputMode="numeric"
          />
        </Field>
        <Field label="Dirección" htmlFor="biz-address">
          <Input id="biz-address" value={f.address} onChange={set('address')} placeholder="Calle 123, Ciudad" />
        </Field>
        <Field label="Teléfono" htmlFor="biz-phone">
          <Input id="biz-phone" value={f.phone} onChange={set('phone')} placeholder="11 0000-0000" />
        </Field>
      </div>
      <Field label="Pie de ticket" htmlFor="biz-footer" hint="Un mensaje corto al final de cada ticket.">
        <Textarea id="biz-footer" value={f.ticket_footer} onChange={set('ticket_footer')} rows={2} maxLength={200} />
      </Field>
    </SettingsCard>
  )
}

export function LoyaltySection({ initial }: { initial: LoyaltySettings }) {
  const [f, setF] = useState(initial)
  const save = useSaveSetting('loyalty', 'Fidelización guardada')
  const valid = validNumbers([
    [f.pesos_per_point, 1, 1_000_000],
    [f.points_per_reward, 1, 1_000_000],
    [f.reward_value_cents, 0, 1_000_000_000],
  ])
  return (
    <SettingsCard
      title="Fidelización"
      description="Los clientes suman puntos con cada compra y los canjean por descuentos."
      onSave={() => save.mutate(f)}
      saving={save.isPending}
      dirty={!same(f, initial) && valid}
    >
      <SwitchRow
        title="Programa de puntos activo"
        description="Si lo desactivás, no se suman ni se canjean puntos."
        control={<Switch checked={f.enabled} onCheckedChange={(v) => setF({ ...f, enabled: v })} />}
      />
      <div className={cn('grid gap-4 sm:grid-cols-3', !f.enabled && 'pointer-events-none opacity-50')}>
        <Field label="Pesos por punto" htmlFor="loy-ppp" hint="Cada cuántos pesos gastados se suma 1 punto.">
          <NumberInput id="loy-ppp" value={f.pesos_per_point} min={1} onChange={(v) => setF({ ...f, pesos_per_point: v })} suffix="$ / pto" />
        </Field>
        <Field label="Puntos para un premio" htmlFor="loy-ppr">
          <NumberInput id="loy-ppr" value={f.points_per_reward} min={1} onChange={(v) => setF({ ...f, points_per_reward: v })} suffix="ptos" />
        </Field>
        <Field label="Valor del premio">
          <MoneyInput value={f.reward_value_cents} onChange={(c) => setF({ ...f, reward_value_cents: c ?? 0 })} />
        </Field>
      </div>
      {valid && f.enabled && (
        <div className="flex items-start gap-3 rounded-xl bg-primary/10 p-4 text-sm">
          <Gift className="mt-0.5 size-5 shrink-0 text-primary" />
          <p>
            Un cliente que gasta <strong className="tabular">{fmtMoney(f.pesos_per_point * f.points_per_reward * 100)}</strong>{' '}
            acumula {fmtNumber(f.points_per_reward, 0)} puntos y gana un descuento de{' '}
            <strong className="tabular">{fmtMoney(f.reward_value_cents)}</strong> (
            {fmtNumber((f.reward_value_cents / (f.pesos_per_point * f.points_per_reward * 100)) * 100, 1)}% de devolución).
          </p>
        </div>
      )}
    </SettingsCard>
  )
}

export function AlertsSection({ initial }: { initial: AlertsSettings }) {
  const [f, setF] = useState(initial)
  const save = useSaveSetting('alerts', 'Umbrales de alertas guardados')
  const valid =
    validNumbers([
      [f.expiry_days, 0, 365],
      [f.supplier_due_days, 0, 365],
      [f.roast_min_days, 0, 120],
      [f.roast_max_days, 1, 365],
    ]) && f.roast_min_days < f.roast_max_days
  return (
    <SettingsCard
      title="Alertas"
      description="Cuándo avisar antes de que algo se venza o se pase."
      onSave={() => save.mutate(f)}
      saving={save.isPending}
      dirty={!same(f, initial) && valid}
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Vencimiento de insumos" htmlFor="al-exp" hint="Avisar estos días antes de que venza un lote.">
          <NumberInput id="al-exp" value={f.expiry_days} min={0} onChange={(v) => setF({ ...f, expiry_days: v })} suffix="días" />
        </Field>
        <Field label="Facturas de proveedores" htmlFor="al-sup" hint="Avisar estos días antes del vencimiento de pago.">
          <NumberInput id="al-sup" value={f.supplier_due_days} min={0} onChange={(v) => setF({ ...f, supplier_due_days: v })} suffix="días" />
        </Field>
        <Field label="Café: reposo mínimo" htmlFor="al-rmin" hint="Días desde el tostado antes de usarlo.">
          <NumberInput id="al-rmin" value={f.roast_min_days} min={0} onChange={(v) => setF({ ...f, roast_min_days: v })} suffix="días" />
        </Field>
        <Field label="Café: frescura máxima" htmlFor="al-rmax" hint="Pasado este tiempo, avisar que está viejo.">
          <NumberInput id="al-rmax" value={f.roast_max_days} min={1} onChange={(v) => setF({ ...f, roast_max_days: v })} suffix="días" />
        </Field>
      </div>
      {!valid && <p className="text-sm text-destructive">Revisá los valores: el reposo mínimo tiene que ser menor que la frescura máxima.</p>}
    </SettingsCard>
  )
}

const ACTION_LABEL: Record<string, string> = {
  create: 'Creó',
  update: 'Modificó',
  delete: 'Eliminó',
  void: 'Anuló',
  restore: 'Restauró',
  login: 'Ingresó',
  open: 'Abrió',
  close: 'Cerró',
}

const auditColumns: ColumnDef<AuditRow, unknown>[] = [
  { accessorKey: 'ts', header: 'Fecha', cell: ({ getValue }) => <span className="tabular whitespace-nowrap">{fmtDateTime(getValue<string>())}</span> },
  { accessorKey: 'user_name', header: 'Usuario', cell: ({ row }) => row.original.user_name ?? (row.original.payload?.by as string | undefined) ?? 'Sistema' },
  {
    accessorKey: 'action',
    header: 'Acción',
    cell: ({ row }) => (
      <span>
        <Badge variant="secondary" className="mr-2">
          {ACTION_LABEL[row.original.action] ?? row.original.action}
        </Badge>
        {row.original.entity}
        {row.original.entity_id != null && <span className="text-muted-foreground"> #{row.original.entity_id}</span>}
      </span>
    ),
  },
  {
    accessorKey: 'payload',
    header: 'Detalle',
    enableSorting: false,
    cell: ({ getValue }) => {
      const p = getValue<Record<string, unknown> | null>()
      if (!p) return <span className="text-muted-foreground">—</span>
      const text = Object.entries(p)
        .map(([k, v]) => `${k}: ${typeof v === 'object' ? JSON.stringify(v) : String(v)}`)
        .join(' · ')
      return <span className="line-clamp-1 max-w-md text-xs text-muted-foreground" title={text}>{text}</span>
    },
  },
]

export function SecuritySection({ initial }: { initial: number }) {
  const [minutes, setMinutes] = useState(initial)
  const save = useSaveSetting('lock_minutes', 'Tiempo de bloqueo guardado')
  const audit = useAudit(true, 200)
  const valid = Number.isInteger(minutes) && minutes >= 1 && minutes <= 240
  return (
    <div className="space-y-4">
      <SettingsCard
        title="Bloqueo automático"
        description="Después de este tiempo sin actividad, la app vuelve a la pantalla de PIN."
        onSave={() => save.mutate(minutes)}
        saving={save.isPending}
        dirty={minutes !== initial && valid}
      >
        <Field label="Minutos de inactividad" htmlFor="lock-min" hint="Entre 1 y 240 minutos." className="max-w-xs">
          <NumberInput id="lock-min" value={minutes} min={1} max={240} onChange={setMinutes} suffix="min" />
        </Field>
      </SettingsCard>
      <SettingsCard title="Registro de actividad" description="Las últimas 200 acciones importantes (quién hizo qué y cuándo).">
        <DataTable columns={auditColumns} data={audit.data} loading={audit.isLoading} searchPlaceholder="Buscar usuario o acción…" pageSize={15} emptyTitle="Sin actividad registrada" />
      </SettingsCard>
    </div>
  )
}

const THEMES: { value: Theme; label: string; icon: typeof Sun; hint: string }[] = [
  { value: 'light', label: 'Claro', icon: Sun, hint: 'Ideal de día' },
  { value: 'dark', label: 'Oscuro', icon: Moon, hint: 'Descansa la vista' },
  { value: 'system', label: 'Sistema', icon: Laptop, hint: 'Sigue a tu equipo' },
]

export function AppearanceSection() {
  const { theme, setTheme } = useTheme()
  return (
    <SettingsCard title="Apariencia" description="Elegí cómo se ve la app en este equipo.">
      <div role="radiogroup" aria-label="Tema" className="grid gap-3 sm:grid-cols-3">
        {THEMES.map(({ value, label, icon: Icon, hint }) => (
          <button
            key={value}
            role="radio"
            aria-checked={theme === value}
            onClick={() => setTheme(value)}
            className={cn(
              'flex items-center gap-3 rounded-2xl border p-4 text-left transition-colors hover:bg-muted/60 focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none',
              theme === value && 'border-primary bg-primary/5 ring-1 ring-primary',
            )}
          >
            <div
              className={cn(
                'flex size-10 items-center justify-center rounded-xl',
                theme === value ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground',
              )}
            >
              <Icon className="size-5" />
            </div>
            <div>
              <p className="font-medium">{label}</p>
              <p className="text-xs text-muted-foreground">{hint}</p>
            </div>
          </button>
        ))}
      </div>
    </SettingsCard>
  )
}
