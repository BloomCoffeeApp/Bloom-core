import type { Level, Order } from './types'

/** Seconds elapsed now, extrapolated from the server's value (avoids clock skew between devices). */
export function liveElapsed(o: Order, fetchedAt: number, now: number): number {
  const running = o.status === 'pending' || o.status === 'received' || o.status === 'preparing'
  return running ? o.elapsed_s + Math.max(0, Math.floor((now - fetchedAt) / 1000)) : o.elapsed_s
}

/** Same rule as backend services/orders.py::timing. */
export function liveLevel(o: Order, elapsed: number, warnPct: number): Level {
  if (o.status === 'pending') return 'pending'
  const target = o.target_minutes * 60
  if (elapsed > target) return 'late'
  return elapsed * 100 >= target * warnPct ? 'warn' : 'ok'
}

export function fmtClock(seconds: number) {
  const s = Math.max(0, Math.floor(seconds))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const ss = String(s % 60).padStart(2, '0')
  return h ? `${h}:${String(m).padStart(2, '0')}:${ss}` : `${m}:${ss}`
}

export function fmtMinutes(seconds: number | null | undefined) {
  if (seconds == null) return '—'
  const m = seconds / 60
  return `${new Intl.NumberFormat('es-AR', { maximumFractionDigits: 1 }).format(m)} min`
}
