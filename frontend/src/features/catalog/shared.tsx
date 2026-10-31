import {
  Apple,
  Beer,
  Cake,
  Coffee,
  Cookie,
  Croissant,
  CupSoda,
  GlassWater,
  IceCream,
  Leaf,
  type LucideIcon,
  Milk,
  Package,
  Pizza,
  Salad,
  Sandwich,
  Soup,
  Wine,
} from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { fmtPct } from '@/lib/format'
import { cn } from '@/lib/utils'

/** Palette names stored in DB (product/category color) → static Tailwind classes. */
export const PALETTE: Record<string, { chip: string; dot: string; tile: string }> = {
  amber: { chip: 'bg-amber-500/15 text-amber-800 dark:text-amber-300', dot: 'bg-amber-500', tile: 'bg-amber-500/15 text-amber-700 dark:text-amber-300' },
  orange: { chip: 'bg-orange-500/15 text-orange-800 dark:text-orange-300', dot: 'bg-orange-500', tile: 'bg-orange-500/15 text-orange-700 dark:text-orange-300' },
  yellow: { chip: 'bg-yellow-500/20 text-yellow-800 dark:text-yellow-300', dot: 'bg-yellow-500', tile: 'bg-yellow-500/20 text-yellow-700 dark:text-yellow-300' },
  lime: { chip: 'bg-lime-500/15 text-lime-800 dark:text-lime-300', dot: 'bg-lime-500', tile: 'bg-lime-500/15 text-lime-700 dark:text-lime-300' },
  emerald: { chip: 'bg-emerald-500/15 text-emerald-800 dark:text-emerald-300', dot: 'bg-emerald-500', tile: 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300' },
  teal: { chip: 'bg-teal-500/15 text-teal-800 dark:text-teal-300', dot: 'bg-teal-500', tile: 'bg-teal-500/15 text-teal-700 dark:text-teal-300' },
  sky: { chip: 'bg-sky-500/15 text-sky-800 dark:text-sky-300', dot: 'bg-sky-500', tile: 'bg-sky-500/15 text-sky-700 dark:text-sky-300' },
  violet: { chip: 'bg-violet-500/15 text-violet-800 dark:text-violet-300', dot: 'bg-violet-500', tile: 'bg-violet-500/15 text-violet-700 dark:text-violet-300' },
  rose: { chip: 'bg-rose-500/15 text-rose-800 dark:text-rose-300', dot: 'bg-rose-500', tile: 'bg-rose-500/15 text-rose-700 dark:text-rose-300' },
  stone: { chip: 'bg-stone-500/15 text-stone-800 dark:text-stone-300', dot: 'bg-stone-500', tile: 'bg-stone-500/15 text-stone-700 dark:text-stone-300' },
}
export const PALETTE_NAMES = Object.keys(PALETTE)
export const palette = (name: string | null | undefined) => PALETTE[name ?? ''] ?? PALETTE.stone

export const CATEGORY_ICONS: Record<string, LucideIcon> = {
  coffee: Coffee,
  milk: Milk,
  'glass-water': GlassWater,
  'cup-soda': CupSoda,
  croissant: Croissant,
  sandwich: Sandwich,
  cake: Cake,
  cookie: Cookie,
  'ice-cream': IceCream,
  salad: Salad,
  pizza: Pizza,
  soup: Soup,
  apple: Apple,
  leaf: Leaf,
  beer: Beer,
  wine: Wine,
  package: Package,
}
export const categoryIcon = (name: string | null | undefined) => CATEGORY_ICONS[name ?? ''] ?? Package

export function CategoryChip({
  category,
  className,
}: {
  category: { name: string; color: string; icon: string } | null
  className?: string
}) {
  if (!category) return <span className="text-xs text-muted-foreground">Sin categoría</span>
  const Icon = categoryIcon(category.icon)
  return (
    <span className={cn('inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium', palette(category.color).chip, className)}>
      <Icon className="size-3" />
      {category.name}
    </span>
  )
}

export type MarginTone = 'good' | 'warn' | 'bad' | 'none'
export const marginTone = (m: number | null | undefined): MarginTone =>
  m == null ? 'none' : m < 35 ? 'bad' : m < 55 ? 'warn' : 'good'

export const marginTextClass = (m: number | null | undefined) =>
  ({
    good: 'text-success',
    warn: 'text-warning-foreground dark:text-warning',
    bad: 'text-destructive',
    none: 'text-muted-foreground',
  })[marginTone(m)]

export function MarginBadge({ margin }: { margin: number | null | undefined }) {
  const tone = marginTone(margin)
  const cls = {
    good: 'bg-success/15 text-success',
    warn: 'bg-warning/20 text-warning-foreground dark:text-warning',
    bad: 'bg-destructive/10 text-destructive',
    none: 'bg-muted text-muted-foreground',
  }[tone]
  return (
    <Badge variant="secondary" className={cn('tabular', cls)}>
      {fmtPct(margin)}
    </Badge>
  )
}

export const marginOf = (price: number, cost: number) => (price > 0 ? ((price - cost) / price) * 100 : null)

export function ColorSwatches({ value, onChange }: { value: string | null; onChange: (c: string) => void }) {
  return (
    <div className="flex flex-wrap gap-2">
      {PALETTE_NAMES.map((c) => (
        <button
          key={c}
          type="button"
          aria-label={c}
          onClick={() => onChange(c)}
          className={cn(
            'size-7 rounded-full ring-offset-2 ring-offset-background transition-all',
            PALETTE[c].dot,
            value === c ? 'ring-2 ring-foreground' : 'opacity-70 hover:opacity-100',
          )}
        />
      ))}
    </div>
  )
}
