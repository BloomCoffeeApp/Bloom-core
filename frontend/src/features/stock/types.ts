export type Unit = 'g' | 'ml' | 'u'
export type StockStatus = 'ok' | 'low' | 'out'
export type MovementType = 'purchase' | 'sale' | 'adjustment' | 'waste' | 'internal' | 'void' | 'count'

export interface StockCategory {
  id: number
  name: string
  item_count: number
}

export interface StockItem {
  id: number
  name: string
  category_id: number | null
  category_name: string | null
  unit: Unit
  current_qty: number
  min_qty: number
  /** Cost per base unit (g/ml/u) in cents — float. */
  avg_cost_cents: number
  default_supplier_id: number | null
  supplier_name: string | null
  track_expiry: boolean
  active: boolean
  status: StockStatus
  value_cents: number
  next_expiry: string | null
  /** Free plan: visible but not usable in recipes or stock movements. */
  locked?: boolean
  /** Package types (stock stays in the base unit); the default one drives "4 × Sachet 1 L + 730 ml". */
  packages: StockPackage[]
}

export interface StockPackage {
  id: number
  name: string
  /** Base units (g/ml/u) per package. */
  content_qty: number
  barcode: string | null
  /** Last price paid per package (cents). */
  cost_cents: number | null
  is_default: boolean
}

export type PackageInput = Omit<StockPackage, 'id' | 'barcode' | 'cost_cents'> & {
  id?: number | null
  barcode?: string | null
  cost_cents?: number | null
}

export type DiscardReason = 'expired' | 'spill' | 'breakage' | 'leftover' | 'other'

export interface DiscardInput {
  stock_item_id: number
  qty?: number
  package_id?: number
  packages?: number
  all?: boolean
  lot_id?: number | null
  reason_code: DiscardReason
  note?: string | null
}

export interface StockLot {
  id: number
  qty_remaining: number
  expiry_date: string | null
  created_at: string
}

/** Lightweight item for the quick discard of the POS / barista. */
export interface QuickItem {
  id: number
  name: string
  unit: Unit
  current_qty: number
  packages: StockPackage[]
}

export interface StockItemInput {
  name: string
  category_id: number | null
  unit: Unit
  min_qty: number
  avg_cost_cents: number
  default_supplier_id: number | null
  track_expiry: boolean
  active?: boolean
  initial_qty?: number
}

export interface Movement {
  id: number
  stock_item_id: number
  type: MovementType
  qty: number
  unit_cost_cents: number
  balance_after: number
  ref_type: string | null
  ref_id: number | null
  reason: string | null
  user_id: number | null
  user_name: string | null
  ts: string
}

export interface StockSummary {
  total_value_cents: number
  low_count: number
  out_count: number
  item_count: number
}

export interface CountItem {
  id: number
  stock_item_id: number
  name: string
  unit: Unit
  category_id: number | null
  category_name: string | null
  expected_qty: number
  counted_qty: number | null
  diff_qty: number | null
  diff_value_cents: number | null
  avg_cost_cents: number
}

export interface InventoryCount {
  id: number
  status: 'open' | 'applied' | 'cancelled'
  notes: string | null
  user_id: number | null
  user_name: string | null
  created_at: string
  updated_at: string | null
  total_items: number
  counted_items: number
  diff_value_cents: number
  items: CountItem[]
}

export interface SuggestionItem {
  stock_item_id: number
  name: string
  unit: Unit
  current_qty: number
  min_qty: number
  status: StockStatus
  daily_consumption: number
  suggested_qty: number
  avg_cost_cents: number
  est_cost_cents: number
}

export interface SuggestionGroup {
  supplier_id: number | null
  supplier_name: string
  items: SuggestionItem[]
  total_est_cents: number
}
