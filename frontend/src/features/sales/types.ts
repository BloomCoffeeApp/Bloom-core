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
  qty: number
  unit_price_cents: number
  discount_cents: number
  total_cents: number
  cost_cents: number
  modifiers: SaleItemModifier[] | null
  notes: string | null
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
  channel: Channel
  table_label: string | null
  cash_session_id: number | null
  user_id: number | null
  user_name: string | null
  customer_id: number | null
  customer_name: string | null
  subtotal_cents: number
  discount_cents: number
  points_discount_cents: number
  total_cents: number
  cost_cents: number
  points_earned: number
  points_redeemed: number
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
  modifier_ids: number[]
  notes?: string | null
  discount_cents?: number
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
