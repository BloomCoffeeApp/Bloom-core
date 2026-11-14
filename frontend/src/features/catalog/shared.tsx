import { Package } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { fmtPct } from '@/lib/format'
import { cn } from '@/lib/utils'

import { CATEGORY_ICONS, marginTone, palette, PALETTE, PALETTE_NAMES } from './catalog-utils'

export function CategoryChip({
  category,
  className,
}: {
  category: { name: string; color: string; icon: string } | null
  className?: string
}) {
  if (!category) return <span className="text-xs text-muted-foreground">Sin categoría</span>
  const Icon = CATEGORY_ICONS[category.icon] ?? Package
  return (
    <span className={cn('inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium', palette(category.color).chip, className)}>
      <Icon className="size-3" />
      {category.name}
    </span>
  )
}

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
            'size-7 rounded-full ring-offset-2 ring-offset-background transition-[transform,box-shadow,border-color,background-color,color] motion-fast',
            PALETTE[c].dot,
            value === c ? 'ring-2 ring-foreground' : 'opacity-70 hover:opacity-100',
          )}
        />
      ))}
    </div>
  )
}
