import { endOfMonth, startOfMonth, subDays, subMonths } from 'date-fns'

import { isoDate } from '@/lib/format'

export interface DateRange {
  from: string
  to: string
}

export type PresetKey = 'today' | 'yesterday' | '7d' | '30d' | 'month' | 'last_month' | '90d'

export const PRESET_LABEL: Record<PresetKey, string> = {
  today: 'Hoy',
  yesterday: 'Ayer',
  '7d': '7 días',
  '30d': '30 días',
  month: 'Mes',
  last_month: 'Mes pasado',
  '90d': '90 días',
}

export function presetRange(p: PresetKey, now = new Date()): DateRange {
  switch (p) {
    case 'today':
      return { from: isoDate(now), to: isoDate(now) }
    case 'yesterday': {
      const y = subDays(now, 1)
      return { from: isoDate(y), to: isoDate(y) }
    }
    case '7d':
      return { from: isoDate(subDays(now, 6)), to: isoDate(now) }
    case '30d':
      return { from: isoDate(subDays(now, 29)), to: isoDate(now) }
    case '90d':
      return { from: isoDate(subDays(now, 89)), to: isoDate(now) }
    case 'month':
      return { from: isoDate(startOfMonth(now)), to: isoDate(now) }
    case 'last_month': {
      const m = subMonths(now, 1)
      return { from: isoDate(startOfMonth(m)), to: isoDate(endOfMonth(m)) }
    }
  }
}

export const CHART_COLORS = ['var(--chart-1)', 'var(--chart-2)', 'var(--chart-3)', 'var(--chart-4)', 'var(--chart-5)']
export const chartColor = (i: number) => CHART_COLORS[i % CHART_COLORS.length]

const compact = new Intl.NumberFormat('es-AR', { notation: 'compact', maximumFractionDigits: 1 })
/** Axis ticks: cents → "$12,5 mil". */
export const fmtMoneyCompact = (cents: number) => `$${compact.format(cents / 100)}`
