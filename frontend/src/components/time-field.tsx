import { Minus, Plus } from 'lucide-react'
import { useId } from 'react'

import { Button } from '@/components/ui/button'
import { DatePicker } from '@/components/date-picker'
import { cn } from '@/lib/utils'

const two = (n: number) => String(n).padStart(2, '0')

/** `HH:MM` → [hours, minutes] (null when empty or not a time). */
const split = (value: string): [number, number] | null => {
  const m = /^(\d{1,2}):(\d{2})/.exec(value ?? '')
  if (!m) return null
  const h = Number(m[1])
  const mi = Number(m[2])
  return h < 24 && mi < 60 ? [h, mi] : null
}

interface TimeFieldProps {
  /** `HH:MM` (24 h) or empty. Same value the browser's time input used, so no API changes. */
  value: string
  onChange: (value: string) => void
  /** Minutes jump by this much with − / + and the arrows (typing accepts any minute). */
  minuteStep?: number
  id?: string
  className?: string
  disabled?: boolean
  'aria-label'?: string
}

/**
 * Time field with Bloom's own − / + buttons (≥ 44 px) for hours and minutes instead of the browser's clock popup.
 * Typing works (two digits each), ArrowUp / ArrowDown step, and hours / minutes wrap around.
 */
export function TimeField({ value, onChange, minuteStep = 5, id, className, disabled, ...rest }: TimeFieldProps) {
  const auto = useId()
  const base = id ?? auto
  const parts = split(value)
  const [h, m] = parts ?? [0, 0]
  const label = rest['aria-label'] ?? 'Hora'

  const set = (nh: number, nm: number) => onChange(`${two(((nh % 24) + 24) % 24)}:${two(((nm % 60) + 60) % 60)}`)
  const bumpH = (dir: 1 | -1) => set(parts ? h + dir : 9, m)
  const bumpM = (dir: 1 | -1) => {
    const next = Math.round((m + dir * minuteStep) / minuteStep) * minuteStep
    if (next >= 60) set(h + 1, 0) // 55 → 00 of the next hour
    else if (next < 0) set(h - 1, 60 - minuteStep)
    else set(h, next)
  }
  const box = (which: 'h' | 'm', current: number, bump: (d: 1 | -1) => void, aria: string) => (
    <input
      id={`${base}-${which}`}
      type="text"
      inputMode="numeric"
      data-slot="input"
      aria-label={aria}
      disabled={disabled}
      value={parts ? two(current) : ''}
      placeholder="--"
      maxLength={2}
      onChange={(e) => {
        const raw = e.target.value.replace(/\D/g, '').slice(0, 2)
        if (raw === '') return onChange('')
        const n = Math.min(Number(raw), which === 'h' ? 23 : 59)
        if (which === 'h') set(n, m)
        else set(h, n)
      }}
      onKeyDown={(e) => {
        if (e.key === 'ArrowUp') {
          e.preventDefault()
          bump(1)
        } else if (e.key === 'ArrowDown') {
          e.preventDefault()
          bump(-1)
        }
      }}
      className={cn(
        'tabular h-11 w-14 rounded-lg border border-input bg-transparent px-1 text-center text-base outline-none transition-colors',
        'focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-50 dark:bg-input/30 md:text-sm',
      )}
    />
  )
  const step = (aria: string, dir: 1 | -1, bump: (d: 1 | -1) => void) => (
    <Button type="button" variant="outline" size="icon" className="size-11 shrink-0" aria-label={aria} disabled={disabled} onClick={() => bump(dir)}>
      {dir === 1 ? <Plus /> : <Minus />}
    </Button>
  )

  return (
    <div role="group" aria-label={label} className={cn('inline-flex flex-wrap items-center gap-1.5', className)} data-testid="time-field">
      {step(`${label}: restar hora`, -1, bumpH)}
      {box('h', h, bumpH, `${label}: horas`)}
      {step(`${label}: sumar hora`, 1, bumpH)}
      <span className="px-0.5 text-lg font-semibold text-muted-foreground" aria-hidden>
        :
      </span>
      {step(`${label}: restar minutos`, -1, bumpM)}
      {box('m', m, bumpM, `${label}: minutos`)}
      {step(`${label}: sumar minutos`, 1, bumpM)}
    </div>
  )
}

interface DateTimeFieldProps {
  /** `YYYY-MM-DDTHH:MM` (what a browser's datetime-local input used) or empty. */
  value: string
  onChange: (value: string) => void
  id?: string
  className?: string
  disabled?: boolean
  min?: string
  'aria-label'?: string
}

/** Date + time with Bloom's own pickers: a `DatePicker` and a `TimeField`, one `YYYY-MM-DDTHH:MM` value. */
export function DateTimeField({ value, onChange, id, className, disabled, min, ...rest }: DateTimeFieldProps) {
  const [date = '', time = ''] = (value ?? '').split('T')
  const label = rest['aria-label'] ?? 'Fecha y hora'
  return (
    <div className={cn('flex flex-wrap items-center gap-2', className)} role="group" aria-label={label}>
      <DatePicker
        id={id}
        value={date}
        min={min?.slice(0, 10)}
        disabled={disabled}
        aria-label={`${label}: fecha`}
        onChange={(d) => onChange(d ? `${d}T${time || '09:00'}` : '')}
      />
      <TimeField value={time.slice(0, 5)} disabled={disabled || !date} aria-label={`${label}: hora`} onChange={(t) => onChange(date && t ? `${date}T${t}` : date ? `${date}T00:00` : '')} />
    </div>
  )
}
