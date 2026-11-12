import { ChevronLeft, ChevronRight } from 'lucide-react'

import { Button } from '@/components/ui/button'

import { monthLabel, shiftMonth } from './utils'

/** ‹ noviembre de 2026 › (can't go past `max`, usually the current month). */
export function MonthPicker({ value, onChange, max }: { value: string; onChange: (m: string) => void; max: string }) {
  return (
    <div className="flex items-center gap-1 rounded-xl border bg-card p-1" data-testid="month-picker">
      <Button variant="ghost" size="icon" aria-label="Mes anterior" onClick={() => onChange(shiftMonth(value, -1))}>
        <ChevronLeft />
      </Button>
      <span className="min-w-36 text-center text-sm font-medium first-letter:uppercase">{monthLabel(value)}</span>
      <Button variant="ghost" size="icon" aria-label="Mes siguiente" disabled={value >= max} onClick={() => onChange(shiftMonth(value, 1))}>
        <ChevronRight />
      </Button>
    </div>
  )
}
