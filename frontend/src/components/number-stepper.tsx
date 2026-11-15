import { Minus, Plus } from 'lucide-react'
import { useId } from 'react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

interface NumberStepperProps {
  /** Kept as text (like the other form fields), so an empty box is allowed while typing. */
  value: string | number
  onChange: (value: string) => void
  min?: number
  max?: number
  step?: number
  /** Short unit shown inside the box after the number ("h", "min", "%"). */
  suffix?: string
  id?: string
  'aria-label'?: string
  className?: string
  disabled?: boolean
}

const clampTo = (n: number, min?: number, max?: number) => Math.min(max ?? Infinity, Math.max(min ?? -Infinity, n))

/** Number field with big − / + buttons (≥ 44 px) instead of the browser's tiny spin arrows.
 * Typing works as usual; ArrowUp / ArrowDown step too. */
export function NumberStepper({ value, onChange, min, max, step = 1, suffix, id, className, disabled, ...rest }: NumberStepperProps) {
  const auto = useId()
  const inputId = id ?? auto
  const current = value === '' || value == null ? NaN : Number(value)

  const bump = (dir: 1 | -1) => {
    const base = Number.isFinite(current) ? current : (min ?? 0)
    onChange(String(clampTo(Math.round((base + dir * step) * 1000) / 1000, min, max)))
  }

  return (
    <div className={cn('inline-flex items-center gap-1.5', className)}>
      <Button
        type="button"
        variant="outline"
        size="icon"
        className="size-11 shrink-0"
        aria-label="Restar"
        disabled={disabled || (min != null && Number.isFinite(current) && current <= min)}
        onClick={() => bump(-1)}
      >
        <Minus />
      </Button>
      <div className="relative">
        <input
          id={inputId}
          type="text"
          inputMode={step < 1 ? 'decimal' : 'numeric'}
          data-slot="input"
          aria-label={rest['aria-label']}
          disabled={disabled}
          value={value ?? ''}
          onChange={(e) => {
            const raw = e.target.value.replace(',', '.')
            if (raw === '' || /^-?\d*\.?\d*$/.test(raw)) onChange(raw)
          }}
          onBlur={() => {
            if (Number.isFinite(current)) onChange(String(clampTo(current, min, max)))
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
            'tabular h-11 w-20 rounded-lg border border-input bg-transparent px-2 text-center text-base outline-none transition-colors',
            'focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-50 dark:bg-input/30 md:text-sm',
            suffix && 'pr-7',
          )}
        />
        {suffix && <span className="pointer-events-none absolute inset-y-0 right-2 flex items-center text-xs text-muted-foreground">{suffix}</span>}
      </div>
      <Button
        type="button"
        variant="outline"
        size="icon"
        className="size-11 shrink-0"
        aria-label="Sumar"
        disabled={disabled || (max != null && Number.isFinite(current) && current >= max)}
        onClick={() => bump(1)}
      >
        <Plus />
      </Button>
    </div>
  )
}
