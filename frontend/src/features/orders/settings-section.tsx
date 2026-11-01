import { useState } from 'react'

import { Switch } from '@/components/ui/switch'

import { Field, NumberInput, SettingsCard, SwitchRow } from '../settings/form'
import { CardSkeleton } from '../settings/form'
import { validNumbers } from '../settings/validation'
import { CHANNEL_LABEL, type Channel } from '../sales/types'
import { useOrdersSettings, useSaveOrdersSettings } from './api'
import type { OrdersSettings } from './types'

const CHANNELS: Channel[] = ['salon', 'llevar', 'delivery']

/** Configuración → Pedidos: which sales go to the order screen and the target time per channel. */
export function OrdersSettingsSection() {
  const q = useOrdersSettings()
  if (!q.data) return <CardSkeleton />
  return <Form initial={q.data} />
}

function Form({ initial }: { initial: OrdersSettings }) {
  const [f, setF] = useState(initial)
  const save = useSaveOrdersSettings()
  const valid = validNumbers([...CHANNELS.map((c) => [f.targets[c], 1, 240] as [number, number, number]), [f.warn_pct, 10, 100]])
  return (
    <SettingsCard
      title="Pantalla de pedidos"
      description="Las ventas del punto de venta pasan solas a la pantalla de la barra o la cocina."
      onSave={() => save.mutate(f)}
      saving={save.isPending}
      dirty={JSON.stringify(f) !== JSON.stringify(initial) && valid}
    >
      <SwitchRow
        title="Mandar las ventas a la pantalla de pedidos"
        description="Las categorías que no se preparan (p. ej. panadería) se excluyen desde Productos → Categorías."
        control={<Switch checked={f.enabled} onCheckedChange={(enabled) => setF({ ...f, enabled })} aria-label="Mandar las ventas a la pantalla de pedidos" />}
      />
      <div className="grid gap-3 sm:grid-cols-3">
        {CHANNELS.map((c) => (
          <div key={c} className="space-y-3 rounded-xl border p-3">
            <div className="flex items-center justify-between gap-2">
              <span className="font-medium">{CHANNEL_LABEL[c]}</span>
              <Switch
                checked={f.channels[c]}
                disabled={!f.enabled}
                onCheckedChange={(v) => setF({ ...f, channels: { ...f.channels, [c]: v } })}
                aria-label={`Mandar ventas de ${CHANNEL_LABEL[c]}`}
              />
            </div>
            <Field label="Tiempo objetivo" htmlFor={`target-${c}`}>
              <NumberInput
                id={`target-${c}`}
                value={f.targets[c]}
                min={1}
                max={240}
                suffix="min"
                onChange={(v) => setF({ ...f, targets: { ...f.targets, [c]: v } })}
              />
            </Field>
          </div>
        ))}
      </div>
      <Field
        label="Pasa a amarillo al llegar al"
        htmlFor="warn-pct"
        hint="Verde mientras está a tiempo, amarillo cerca del objetivo y rojo (atrasado) cuando lo supera."
      >
        <NumberInput id="warn-pct" value={f.warn_pct} min={10} max={100} suffix="% del objetivo" onChange={(warn_pct) => setF({ ...f, warn_pct })} className="max-w-56" />
      </Field>
    </SettingsCard>
  )
}
