import { fmtNumber, fmtQty } from '@/lib/format'

import type { DiscardReason, MovementType, StockPackage, StockStatus, Unit } from './types'

// ------------------------------------------------------------------ unit helpers
export const UNIT_NAME: Record<Unit, string> = { g: 'gramos', ml: 'mililitros', u: 'unidades' }
/** Unit used for prices/purchases: kg, L or u. */
export const bulkUnit = (u: Unit) => (u === 'g' ? 'kg' : u === 'ml' ? 'L' : 'u')
export const bulkFactor = (u: Unit) => (u === 'u' ? 1 : 1000)
/** Cost per kg / L / u in cents from cost per base unit. */
export const bulkCost = (costPerBase: number, u: Unit) => Math.round(costPerBase * bulkFactor(u))

export const MOVEMENT_LABEL: Record<MovementType, string> = {
  purchase: 'Compra',
  sale: 'Venta',
  adjustment: 'Ajuste',
  waste: 'Merma',
  internal: 'Consumo interno',
  void: 'Anulación',
  count: 'Conteo físico',
}

export const STATUS_LABEL: Record<StockStatus, string> = { ok: 'OK', low: 'Bajo mínimo', out: 'Sin stock' }

// ------------------------------------------------------------------ packages
/** The package used to show and count stock (the default one, else the first). */
export const defaultPackage = (packages: StockPackage[] | undefined) => packages?.find((p) => p.is_default) ?? packages?.[0]

/** Splits a base quantity into whole packages + the loose rest. */
export function splitPackages(qty: number, pkg: StockPackage) {
  const whole = qty > 0 ? Math.floor((qty + 1e-6) / pkg.content_qty) : 0
  const rest = Math.round((qty - whole * pkg.content_qty) * 1000) / 1000
  return { whole, rest }
}

/** "4 × Sachet 1 L + 730 ml" (or the plain quantity when the item has no packages / stock ≤ 0). */
export function fmtPackages(qty: number, unit: Unit, packages: StockPackage[] | undefined) {
  const pkg = defaultPackage(packages)
  if (!pkg || qty <= 0) return fmtQty(qty, unit)
  const { whole, rest } = splitPackages(qty, pkg)
  if (!whole) return fmtQty(qty, unit)
  const head = `${fmtNumber(whole, 0)} × ${pkg.name}`
  return rest > 0 ? `${head} + ${fmtQty(rest, unit)}` : head
}

/** Base units from packages + loose amount (counts, purchases). */
export const fromPackages = (packages: number, pkg: StockPackage, loose = 0) =>
  Math.round((packages * pkg.content_qty + loose) * 10000) / 10000

export const DISCARD_REASONS: { value: DiscardReason; label: string }[] = [
  { value: 'expired', label: 'Vencido' },
  { value: 'spill', label: 'Derrame / se cayó' },
  { value: 'breakage', label: 'Rotura' },
  { value: 'leftover', label: 'Sobrante de preparación' },
  { value: 'other', label: 'Otro' },
]
