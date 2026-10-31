// Category/product colors are stored as Tailwind palette names (e.g. "amber"). Classes are listed
// literally so Tailwind can detect them.
const TILE: Record<string, { tile: string; dot: string }> = {
  amber: { tile: 'bg-amber-500/10 border-amber-500/30 hover:bg-amber-500/20', dot: 'bg-amber-500' },
  orange: { tile: 'bg-orange-500/10 border-orange-500/30 hover:bg-orange-500/20', dot: 'bg-orange-500' },
  yellow: { tile: 'bg-yellow-500/10 border-yellow-500/30 hover:bg-yellow-500/20', dot: 'bg-yellow-500' },
  lime: { tile: 'bg-lime-500/10 border-lime-500/30 hover:bg-lime-500/20', dot: 'bg-lime-500' },
  green: { tile: 'bg-green-500/10 border-green-500/30 hover:bg-green-500/20', dot: 'bg-green-500' },
  emerald: { tile: 'bg-emerald-500/10 border-emerald-500/30 hover:bg-emerald-500/20', dot: 'bg-emerald-500' },
  teal: { tile: 'bg-teal-500/10 border-teal-500/30 hover:bg-teal-500/20', dot: 'bg-teal-500' },
  cyan: { tile: 'bg-cyan-500/10 border-cyan-500/30 hover:bg-cyan-500/20', dot: 'bg-cyan-500' },
  sky: { tile: 'bg-sky-500/10 border-sky-500/30 hover:bg-sky-500/20', dot: 'bg-sky-500' },
  blue: { tile: 'bg-blue-500/10 border-blue-500/30 hover:bg-blue-500/20', dot: 'bg-blue-500' },
  indigo: { tile: 'bg-indigo-500/10 border-indigo-500/30 hover:bg-indigo-500/20', dot: 'bg-indigo-500' },
  violet: { tile: 'bg-violet-500/10 border-violet-500/30 hover:bg-violet-500/20', dot: 'bg-violet-500' },
  purple: { tile: 'bg-purple-500/10 border-purple-500/30 hover:bg-purple-500/20', dot: 'bg-purple-500' },
  fuchsia: { tile: 'bg-fuchsia-500/10 border-fuchsia-500/30 hover:bg-fuchsia-500/20', dot: 'bg-fuchsia-500' },
  pink: { tile: 'bg-pink-500/10 border-pink-500/30 hover:bg-pink-500/20', dot: 'bg-pink-500' },
  rose: { tile: 'bg-rose-500/10 border-rose-500/30 hover:bg-rose-500/20', dot: 'bg-rose-500' },
  red: { tile: 'bg-red-500/10 border-red-500/30 hover:bg-red-500/20', dot: 'bg-red-500' },
  stone: { tile: 'bg-stone-500/10 border-stone-500/30 hover:bg-stone-500/20', dot: 'bg-stone-500' },
  slate: { tile: 'bg-slate-500/10 border-slate-500/30 hover:bg-slate-500/20', dot: 'bg-slate-500' },
}

const FALLBACK = { tile: 'bg-card border-border hover:bg-muted', dot: 'bg-primary' }

export const colorClasses = (color: string | null | undefined) => (color && TILE[color]) || FALLBACK
