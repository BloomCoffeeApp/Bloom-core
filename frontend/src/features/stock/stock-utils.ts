import type { MovementType, StockStatus, Unit } from './types'

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
