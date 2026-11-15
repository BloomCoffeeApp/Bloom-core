import { useState } from 'react'

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

import { NO_YEAR } from './birthday-utils'

const MONTHS = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']

const pad = (n: number) => String(n).padStart(2, '0')
const daysIn = (month: number, year: number) => new Date(year, month, 0).getDate()

interface BirthdayFieldProps {
  /** `YYYY-MM-DD` or empty. */
  value: string
  onChange: (value: string) => void
  id?: string
}

/** Day + month, and an optional year (people often don't want to give it). */
export function BirthdayField({ value, onChange, id }: BirthdayFieldProps) {
  const [y, m, d] = value ? value.split('-').map(Number) : [0, 0, 0]
  const hasYear = !!value && y !== NO_YEAR
  const [thisYear] = useState(() => new Date().getFullYear())
  const years = Array.from({ length: thisYear - 1919 }, (_, i) => thisYear - i)

  const emit = (day: number, month: number, year: number | null) => {
    if (!day || !month) return onChange('')
    const yy = year ?? NO_YEAR
    onChange(`${yy}-${pad(month)}-${pad(Math.min(day, daysIn(month, yy)))}`)
  }

  return (
    <div className="grid grid-cols-[4.5rem_1fr_6.5rem] gap-2" role="group" aria-label="Cumpleaños">
      <Select value={d ? String(d) : ''} onValueChange={(v) => emit(Number(v), m || 1, hasYear ? y : null)}>
        <SelectTrigger id={id} className="h-11 w-full" aria-label="Día">
          <SelectValue placeholder="Día" />
        </SelectTrigger>
        <SelectContent>
          {Array.from({ length: 31 }, (_, i) => i + 1).map((n) => (
            <SelectItem key={n} value={String(n)}>
              {n}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <Select value={m ? String(m) : ''} onValueChange={(v) => emit(d || 1, Number(v), hasYear ? y : null)}>
        <SelectTrigger className="h-11 w-full" aria-label="Mes">
          <SelectValue placeholder="Mes" />
        </SelectTrigger>
        <SelectContent>
          {MONTHS.map((name, i) => (
            <SelectItem key={name} value={String(i + 1)} className="capitalize">
              {name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <Select value={hasYear ? String(y) : 'none'} onValueChange={(v) => emit(d, m, v === 'none' ? null : Number(v))} disabled={!d || !m}>
        <SelectTrigger className="h-11 w-full" aria-label="Año (opcional)">
          <SelectValue placeholder="Año" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="none">Sin año</SelectItem>
          {years.map((n) => (
            <SelectItem key={n} value={String(n)}>
              {n}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}
