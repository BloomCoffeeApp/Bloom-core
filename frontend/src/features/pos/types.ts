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
export interface PosProduct {
  id: number
  name: string
  price_cents: number
  category_id: number | null
  color: string | null
  image_path: string | null
  modifier_groups: PosModifierGroup[]
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
}

// GET /api/pos/config
export interface PosConfig {
  loyalty: { enabled: boolean; pesos_per_point: number; points_per_reward: number; reward_value_cents: number }
  can_discount: boolean
}

export interface CartLine {
  key: string
  product_id: number
  category_id: number | null
  name: string
  unit_cents: number
  modifiers: PosModifier[]
  qty: number
  notes: string
  discount_cents: number
}

export interface CartState {
  lines: CartLine[]
  channel: Channel
  table_label: string
  customer: PosCustomer | null
  discount: { mode: 'amount' | 'pct'; value: number }
  points_to_redeem: number
}
