export const AVATAR_COLORS: Record<string, string> = {
  amber: 'bg-amber-500/20 text-amber-700 dark:text-amber-300',
  sky: 'bg-sky-500/20 text-sky-700 dark:text-sky-300',
  emerald: 'bg-emerald-500/20 text-emerald-800 dark:text-emerald-300',
  violet: 'bg-violet-500/20 text-violet-700 dark:text-violet-300',
  rose: 'bg-rose-500/20 text-rose-700 dark:text-rose-300',
  orange: 'bg-orange-500/20 text-orange-700 dark:text-orange-300',
}

export const initials = (name: string) =>
  name
    .split(/\s+/)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join('')
