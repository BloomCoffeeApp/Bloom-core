import {
  addDays,
  addMonths,
  addYears,
  format,
  isSameDay,
  isSameMonth,
  isValid,
  parseISO,
  startOfMonth,
  startOfWeek,
} from 'date-fns'
import { es } from 'date-fns/locale'
import { CalendarDays, ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { cn } from '@/lib/utils'

const ISO = 'yyyy-MM-dd'
const WEEKDAYS = ['L', 'M', 'M', 'J', 'V', 'S', 'D']

const toDate = (value: string | null | undefined): Date | null => {
  if (!value) return null
  const d = parseISO(value.slice(0, 10))
  return isValid(d) ? d : null
}

interface DatePickerProps {
  /** `YYYY-MM-DD` or empty. Same value the browser's date input used, so no API changes. */
  value: string
  onChange: (value: string) => void
  min?: string
  max?: string
  id?: string
  className?: string
  placeholder?: string
  /** Shows «Borrar» (the field may stay empty). */
  clearable?: boolean
  disabled?: boolean
  title?: string
  'aria-label'?: string
}

/** Date field with Bloom's own calendar (Spanish, week from Monday, keyboard, light/dark) instead of the
 * browser's default one. Arrow keys move by day / week, PageUp / PageDown by month, Enter picks. */
export function DatePicker({
  value,
  onChange,
  min,
  max,
  id,
  className,
  placeholder = 'Elegir fecha',
  clearable = false,
  disabled,
  ...rest
}: DatePickerProps) {
  const selected = toDate(value)
  const minD = toDate(min)
  const maxD = toDate(max)
  const [open, setOpen] = useState(false)
  const [focusDay, setFocusDay] = useState<Date>(selected ?? new Date())
  const gridRef = useRef<HTMLDivElement>(null)
  const today = new Date()

  const inRange = (d: Date) => (!minD || d >= minD) && (!maxD || d <= maxD)

  useEffect(() => {
    if (open) setFocusDay(selected ?? new Date())
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  // Keeps the keyboard focus on the focused day after moving (also across months).
  useEffect(() => {
    if (!open) return
    const el = gridRef.current?.querySelector<HTMLButtonElement>(`[data-day="${format(focusDay, ISO)}"]`)
    el?.focus()
  }, [focusDay, open])

  const days = useMemo(() => {
    const start = startOfWeek(startOfMonth(focusDay), { weekStartsOn: 1 })
    return Array.from({ length: 42 }, (_, i) => addDays(start, i))
  }, [focusDay])

  const pick = (d: Date) => {
    if (!inRange(d)) return
    onChange(format(d, ISO))
    setOpen(false)
  }

  const onGridKey = (e: React.KeyboardEvent) => {
    const moves: Record<string, () => Date> = {
      ArrowLeft: () => addDays(focusDay, -1),
      ArrowRight: () => addDays(focusDay, 1),
      ArrowUp: () => addDays(focusDay, -7),
      ArrowDown: () => addDays(focusDay, 7),
      PageUp: () => addMonths(focusDay, e.shiftKey ? -12 : -1),
      PageDown: () => addMonths(focusDay, e.shiftKey ? 12 : 1),
      Home: () => startOfWeek(focusDay, { weekStartsOn: 1 }),
      End: () => addDays(startOfWeek(focusDay, { weekStartsOn: 1 }), 6),
    }
    const move = moves[e.key]
    if (move) {
      e.preventDefault()
      setFocusDay(move())
    }
  }

  const title = format(focusDay, "MMMM 'de' yyyy", { locale: es })

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          id={id}
          type="button"
          variant="outline"
          disabled={disabled}
          aria-label={rest['aria-label'] ? `${rest['aria-label']}: ${selected ? format(selected, "d 'de' MMM yyyy", { locale: es }) : placeholder}` : undefined}
          title={rest.title}
          data-value={value}
          className={cn('h-11 w-full min-w-40 justify-start gap-2 px-3 font-normal', !selected && 'text-muted-foreground', className)}
        >
          <CalendarDays className="size-4 shrink-0 text-muted-foreground" />
          <span className="truncate">{selected ? format(selected, "d 'de' MMM yyyy", { locale: es }) : placeholder}</span>
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" data-testid="date-picker-popover" className="w-[19.5rem] gap-2 p-3" onOpenAutoFocus={(e) => {
          e.preventDefault()
          gridRef.current?.querySelector<HTMLButtonElement>('[data-day][tabindex="0"]')?.focus()
        }}>
        <div className="flex items-center justify-between gap-1">
          <div className="flex">
            <Button type="button" variant="ghost" size="icon-sm" aria-label="Año anterior" onClick={() => setFocusDay(addYears(focusDay, -1))}>
              <ChevronsLeft />
            </Button>
            <Button type="button" variant="ghost" size="icon-sm" aria-label="Mes anterior" onClick={() => setFocusDay(addMonths(focusDay, -1))}>
              <ChevronLeft />
            </Button>
          </div>
          <div className="text-sm font-semibold first-letter:uppercase" aria-live="polite">
            {title}
          </div>
          <div className="flex">
            <Button type="button" variant="ghost" size="icon-sm" aria-label="Mes siguiente" onClick={() => setFocusDay(addMonths(focusDay, 1))}>
              <ChevronRight />
            </Button>
            <Button type="button" variant="ghost" size="icon-sm" aria-label="Año siguiente" onClick={() => setFocusDay(addYears(focusDay, 1))}>
              <ChevronsRight />
            </Button>
          </div>
        </div>
        <div className="grid grid-cols-7 text-center text-xs text-muted-foreground" aria-hidden>
          {WEEKDAYS.map((d, i) => (
            <div key={i} className="py-1">
              {d}
            </div>
          ))}
        </div>
        <div ref={gridRef} role="grid" aria-label={title} className="grid grid-cols-7 gap-0.5" onKeyDown={onGridKey}>
          {days.map((d) => {
            const isSel = !!selected && isSameDay(d, selected)
            const isToday = isSameDay(d, today)
            const outside = !isSameMonth(d, focusDay)
            const ok = inRange(d)
            return (
              <button
                key={d.toISOString()}
                type="button"
                role="gridcell"
                data-day={format(d, ISO)}
                tabIndex={isSameDay(d, focusDay) ? 0 : -1}
                disabled={!ok}
                aria-selected={isSel}
                aria-label={format(d, "EEEE d 'de' MMMM 'de' yyyy", { locale: es })}
                onClick={() => pick(d)}
                className={cn(
                  'tabular flex size-10 items-center justify-center rounded-lg text-sm outline-none transition-colors',
                  'hover:bg-accent focus-visible:ring-3 focus-visible:ring-ring/50 disabled:pointer-events-none disabled:opacity-30',
                  outside && !isSel && 'text-muted-foreground/60',
                  isToday && !isSel && 'font-semibold ring-1 ring-primary/60',
                  isSel && 'bg-primary font-semibold text-primary-foreground hover:bg-primary',
                )}
              >
                {d.getDate()}
              </button>
            )
          })}
        </div>
        <div className="flex items-center justify-between pt-1">
          <Button type="button" variant="ghost" size="sm" disabled={!inRange(today)} onClick={() => pick(today)}>
            Hoy
          </Button>
          {clearable && !!value && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => {
                onChange('')
                setOpen(false)
              }}
            >
              Borrar
            </Button>
          )}
        </div>
      </PopoverContent>
    </Popover>
  )
}
