import { BRAND } from '@/lib/brand'
import { cn } from '@/lib/utils'

/** App mark (cup + blooming flower). Mirrors public/logo.svg; colors from brand.json. */
export function Logo({ className }: { className?: string }) {
  const { primary, accent, background } = BRAND.colors
  return (
    <svg viewBox="0 0 64 64" className={cn('size-8 shrink-0', className)} role="img" aria-label={BRAND.name}>
      <rect width="64" height="64" rx="14" fill={primary} />
      <g transform="translate(32 20)" fill={background}>
        {[0, 72, 144, 216, 288].map((r) => (
          <ellipse key={r} cy="-6.2" rx="3.7" ry="6.2" transform={`rotate(${r})`} />
        ))}
        <circle r="3.2" fill={accent} />
      </g>
      <path d="M15 33h32v5a12 12 0 0 1-12 12h-8a12 12 0 0 1-12-12z" fill={background} />
      <path d="M47 35.5h2.5a5 5 0 0 1 0 10H46" fill="none" stroke={background} strokeWidth="3" strokeLinecap="round" />
      <rect x="11" y="52.5" width="40" height="3" rx="1.5" fill={background} opacity="0.8" />
    </svg>
  )
}
