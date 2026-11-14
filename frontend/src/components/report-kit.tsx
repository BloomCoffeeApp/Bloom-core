import { CalendarRange } from 'lucide-react'
import type { ReactNode } from 'react'

import { Input } from '@/components/ui/input'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { type DateRange, PRESET_LABEL, type PresetKey, presetRange } from '@/components/report-utils'
import { fmtMoney } from '@/lib/format'
import { cn } from '@/lib/utils'

/** Segmented preset selector ("Hoy / Ayer / 7 días …"). */
export function PresetToggle({
  value,
  onChange,
  presets,
  className,
}: {
  value: PresetKey | null
  onChange: (p: PresetKey) => void
  presets: PresetKey[]
  className?: string
}) {
  return (
    <ToggleGroup
      type="single"
      variant="outline"
      spacing={0}
      value={value ?? ''}
      onValueChange={(v) => v && onChange(v as PresetKey)}
      className={cn('bg-card', className)}
    >
      {presets.map((p) => (
        <ToggleGroupItem key={p} value={p} className="px-3 text-xs sm:text-sm">
          {PRESET_LABEL[p]}
        </ToggleGroupItem>
      ))}
    </ToggleGroup>
  )
}

/** Presets + free from/to date inputs. */
export function RangePicker({
  range,
  preset,
  onChange,
}: {
  range: DateRange
  preset: PresetKey | null
  onChange: (r: DateRange, preset: PresetKey | null) => void
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <PresetToggle
        value={preset}
        presets={['today', 'yesterday', '7d', '30d', 'month', 'last_month', '90d']}
        onChange={(p) => onChange(presetRange(p), p)}
      />
      <div className="flex items-center gap-1.5 rounded-lg border bg-card px-2 py-1">
        <CalendarRange className="size-4 text-muted-foreground" />
        <Input
          type="date"
          aria-label="Desde"
          value={range.from}
          max={range.to}
          onChange={(e) => e.target.value && onChange({ ...range, from: e.target.value }, null)}
          className="h-7 w-36 border-0 bg-transparent px-1 shadow-none focus-visible:ring-0 dark:bg-transparent"
        />
        <span className="text-xs text-muted-foreground">a</span>
        <Input
          type="date"
          aria-label="Hasta"
          value={range.to}
          min={range.from}
          onChange={(e) => e.target.value && onChange({ ...range, to: e.target.value }, null)}
          className="h-7 w-36 border-0 bg-transparent px-1 shadow-none focus-visible:ring-0 dark:bg-transparent"
        />
      </div>
    </div>
  )
}

interface TooltipItem {
  name?: string | number
  value?: unknown
  color?: string
  dataKey?: unknown
  payload?: unknown
}

/** Recharts tooltip that formats every value as money. Use as `content={<MoneyTooltip />}`. */
export function MoneyTooltip({
  active,
  payload,
  label,
  labels,
  valueFormatter = (v) => fmtMoney(v),
}: {
  active?: boolean
  payload?: readonly TooltipItem[]
  label?: ReactNode
  labels?: Record<string, string>
  valueFormatter?: (v: number) => string
}) {
  if (!active || !payload?.length) return null
  return (
    <div className="grid min-w-36 gap-1.5 rounded-lg border bg-background px-3 py-2 text-xs shadow-xl">
      {label != null && label !== '' && <div className="font-medium">{label}</div>}
      {payload.map((item, i) => {
        const key = String(item.dataKey ?? item.name ?? i)
        return (
          <div key={key + i} className="flex items-center justify-between gap-4">
            <span className="flex items-center gap-1.5 text-muted-foreground">
              <span className="size-2.5 rounded-[3px]" style={{ background: item.color }} />
              {labels?.[key] ?? item.name}
            </span>
            <span className="tabular font-medium">{valueFormatter(Number(item.value ?? 0))}</span>
          </div>
        )
      })}
    </div>
  )
}

/** Horizontal share bar list (used for top products, mixes). */
export function BarList({
  items,
  valueLabel,
}: {
  items: { key: string; label: string; value: number; hint?: string }[]
  valueLabel?: (v: number) => string
}) {
  const max = Math.max(1, ...items.map((i) => i.value))
  return (
    <ul className="space-y-2.5">
      {items.map((it, idx) => (
        <li key={it.key} className="space-y-1">
          <div className="flex items-baseline justify-between gap-3 text-sm">
            <span className="truncate">
              <span className="mr-2 text-xs text-muted-foreground tabular">{idx + 1}</span>
              {it.label}
            </span>
            <span className="tabular shrink-0 font-medium">
              {valueLabel ? valueLabel(it.value) : fmtMoney(it.value)}
              {it.hint && <span className="ml-2 text-xs font-normal text-muted-foreground">{it.hint}</span>}
            </span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-primary/80 transition-[width] motion-base"
              style={{ width: `${Math.max(2, (it.value / max) * 100)}%` }}
            />
          </div>
        </li>
      ))}
    </ul>
  )
}
