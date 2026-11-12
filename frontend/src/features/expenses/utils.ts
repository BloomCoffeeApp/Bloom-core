import { format, parse } from 'date-fns'
import { es } from 'date-fns/locale'

import type { ExpenseKind } from './types'

export const KIND_LABEL: Record<ExpenseKind, string> = {
  fixed: 'Fijo',
  variable: 'Variable',
}

export const currentMonth = (now: Date = new Date()) => format(now, 'yyyy-MM')

export function shiftMonth(m: string, n: number) {
  const d = parse(`${m}-01`, 'yyyy-MM-dd', new Date(2000, 0, 1))
  d.setMonth(d.getMonth() + n)
  return format(d, 'yyyy-MM')
}

/** "noviembre de 2026" */
export const monthLabel = (m: string) => format(parse(`${m}-01`, 'yyyy-MM-dd', new Date(2000, 0, 1)), "MMMM 'de' yyyy", { locale: es })
