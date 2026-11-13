// Mirrors backend/app/schemas/sales.py

export type Channel = 'salon' | 'llevar' | 'delivery'
export type SaleStatus = 'completed' | 'voided'

export const CHANNEL_LABEL: Record<Channel, string> = {
  salon: 'Salón',
  llevar: 'Para llevar',
  delivery: 'Delivery',
}

export interface PaymentMethod {
  id: number
  code: string
  name: string
  surcharge_pct: number
  sort_order: number
}

export interface SaleItemModifier {
  id: number
  name: string
  price_delta_cents: number
}

export interface SaleItem {
  id: number
  product_id: number | null
  name_snapshot: string
  /** Size sold (snapshot at sale time), null for products without sizes. */
  size_id: number | null
  size_name: string | null
  qty: number
  unit_price_cents: number
  discount_cents: number
  total_cents: number
  cost_cents: number
  modifiers: SaleItemModifier[] | null
  notes: string | null
  /** Pro promos: name and amount of the promotion applied (part of discount_cents). */
  promo_name?: string | null
  promo_discount_cents?: number
  /** Pro loyalty: free product of a stamp card ("Premio fidelidad"). */
  reward_program_id?: number | null
  courtesy_reason?: string | null
}

export interface SalePayment {
  id: number
  method: string
  amount_cents: number
  tendered_cents: number | null
  change_cents: number
}

export interface Sale {
  id: number
  number: number
  ts: string
  status: SaleStatus
  /** Courtesy ("invita la casa"): total 0, stock moved; courtesy_cents = menu value given away. */
  is_courtesy: boolean
  courtesy_cents: number
  courtesy_reason: string | null
  channel: Channel
  table_label: string | null
  cash_session_id: number | null
  user_id: number | null
  user_name: string | null
  customer_id: number | null
  customer_name: string | null
  subtotal_cents: number
  delivery_fee_cents: number
  /** Optional tip paid on top of the total (not part of `total_cents`). */
  tip_cents: number
  discount_cents: number
  points_discount_cents: number
  total_cents: number
  cost_cents: number
  points_earned: number
  points_redeemed: number
  /** Pro loyalty: stamp-card discount reward (included in discount_cents). */
  reward_discount_cents?: number
  notes: string | null
  void_reason: string | null
  voided_by: number | null
  voided_by_name: string | null
  voided_at: string | null
  methods: string[]
  items_count: number
}

export interface SaleDetail extends Sale {
  items: SaleItem[]
  payments: SalePayment[]
  customer: { id: number; name: string; phone: string | null; points: number; balance_cents: number } | null
  change_cents: number
  /** Set while the sale is completed and charged a table's tab: voiding it reopens that tab. */
  table_tab?: { id: number; table_label: string | null } | null
}

export interface SaleList {
  items: Sale[]
  total: number
  page: number
  page_size: number
  sum_total_cents: number
}

export interface Business {
  name?: string
  cuit?: string
  address?: string
  phone?: string
  ticket_footer?: string
}

export interface TicketData {
  business: Business
  sale: SaleDetail
  payment_names: Record<string, string>
}

export interface SaleItemIn {
  product_id: number
  qty: number
  /** Required for sized products (null/absent = the default size). */
  size_id?: number | null
  modifier_ids: number[]
  notes?: string | null
  discount_cents?: number
  /** false = already sent to the bar (a table's tab). */
  to_bar?: boolean
  /** Pro loyalty: this line is a stamp-card reward ($0). */
  reward_program_id?: number | null
}

export interface PaymentIn {
  method: string
  amount_cents: number
  tendered_cents?: number | null
}

export interface SaleIn {
  items: SaleItemIn[]
  customer_id?: number | null
  channel: Channel
  table_label?: string | null
  discount_cents?: number
  discount_pct?: number | null
  points_to_redeem?: number
  payments: PaymentIn[]
  notes?: string | null
  is_courtesy?: boolean
  courtesy_reason?: string | null
  /** Charging a table's open tab: it closes with this sale. */
  tab_id?: number | null
  /** Optional tip on top of the total (the payments cover total + tip). */
  tip_cents?: number
  /** Pro loyalty: stamp-card reward that discounts the sale. */
  reward_program_id?: number | null
}

export interface SalesFilters {
  date_from?: string
  date_to?: string
  status?: string
  method?: string
  number?: number
  page: number
  page_size: number
}
