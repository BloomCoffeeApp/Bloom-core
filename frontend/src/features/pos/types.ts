import type { Channel } from '../sales/types'

// GET /api/pos/catalog (catalog module)
export interface PosModifier {
  id: number
  name: string
  price_delta_cents: number
}
export interface PosModifierGroup {
  id: number
  name: string
  min_select: number
  max_select: number
  modifiers: PosModifier[]
}
export interface PosCategory {
  id: number
  name: string
  color: string
  icon: string
}
/** A size the product is sold in (price of the size; modifiers add on top). */
export interface PosSize {
  size_id: number
  name: string
  short_label: string
  volume_ml: number | null
  price_cents: number
  is_default: boolean
}
export interface PosProduct {
  id: number
  name: string
  price_cents: number
  category_id: number | null
  color: string | null
  image_path: string | null
  modifier_groups: PosModifierGroup[]
  /** Empty = no size choice. */
  sizes: PosSize[]
}
export interface PosCatalog {
  categories: PosCategory[]
  products: PosProduct[]
}

// GET /api/customers?q= (customers module)
export interface PosCustomer {
  id: number
  name: string
  phone: string | null
  points: number
  balance_cents: number
  credit_limit_cents: number
  /** Free plan: can't be the customer of a sale. */
  locked?: boolean
}

// GET /api/pos/config
export interface PosConfig {
  loyalty: { enabled: boolean; pesos_per_point: number; points_per_reward: number; reward_value_cents: number }
  can_discount: boolean
  /** Optional tips (Configuración → Propinas). */
  tips?: { enabled: boolean; percents: number[] }
}

export interface CartLine {
  key: string
  product_id: number
  category_id: number | null
  name: string
  /** Chosen size (null for products without sizes). */
  size: { size_id: number; name: string; short_label: string } | null
  unit_cents: number
  modifiers: PosModifier[]
  qty: number
  notes: string
  discount_cents: number
  /** false = already sent to the bar (loaded from a table's open tab). */
  to_bar?: boolean
  /** Stamp-card reward line (Pro loyalty): $0, "Premio fidelidad". */
  reward?: { program_id: number; label: string } | null
}

/** POST /api/pos/quote: automatic promotion of each cart line (Pro promos; none in the free edition). */
export interface QuoteLine {
  index: number
  promo_id: number | null
  promo_name: string | null
  discount_cents: number
}

export interface CartState {
  lines: CartLine[]
  channel: Channel
  table_label: string
  customer: PosCustomer | null
  discount: { mode: 'amount' | 'pct'; value: number }
  points_to_redeem: number
  /** Charging a table's open tab ("mesa abierta"). */
  /** `prepaid_cents`: already paid from the table's phones (Mercado Pago); the cashier collects the rest. */
  tab?: { id: number; label: string; prepaid_cents?: number } | null
  /** Stamp-card discount reward on the whole sale (Pro loyalty). */
  reward?: { program_id: number; label: string; kind: 'pct' | 'fixed'; value: number } | null
}
