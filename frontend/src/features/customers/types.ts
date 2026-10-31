export type Segment = 'todos' | 'frecuentes' | 'inactivos' | 'cumpleanos_mes' | 'deudores'

export interface Customer {
  id: number
  name: string
  phone: string | null
  email: string | null
  birthday: string | null
  notes: string | null
  points: number
  balance_cents: number
  credit_limit_cents: number
  active: boolean
  created_at: string
}

export interface CustomerListItem extends Customer {
  last_visit_at: string | null
  visits: number
  visits_30d: number
  total_spent_cents: number
}

export interface FavoriteProduct {
  product_id: number | null
  name: string
  qty: number
}

export interface CustomerMetrics {
  total_spent_cents: number
  tickets: number
  avg_ticket_cents: number
  first_visit_at: string | null
  last_visit_at: string | null
  days_since_last_visit: number | null
  visits_per_month: number
  visits_30d: number
  favorite_product: FavoriteProduct | null
  top_products: FavoriteProduct[]
}

export interface AccountMovement {
  id: number
  amount_cents: number
  type: 'charge' | 'payment' | 'void' | string
  method: string | null
  sale_id: number | null
  user_id: number | null
  ts: string
}

export interface LoyaltyTx {
  id: number
  points: number
  reason: string
  sale_id: number | null
  ts: string
}

export interface CustomerDetail extends Customer {
  metrics: CustomerMetrics
  account_movements: AccountMovement[]
  loyalty_transactions: LoyaltyTx[]
  over_limit: boolean
}

export interface CustomerSale {
  id: number
  number: number
  ts: string
  total_cents: number
  status: string
  channel: string
  items_count: number
  items_summary: string
  payment_methods: string[]
}

export interface CustomerSalesPage {
  items: CustomerSale[]
  total: number
  page: number
  page_size: number
}

export interface CustomerStats {
  total: number
  activos_30d: number
  nuevos_mes: number
  deuda_total_cents: number
  deudores: number
  cumpleanos_hoy: { id: number; name: string; phone: string | null }[]
}

export interface CustomerInput {
  name: string
  phone?: string | null
  email?: string | null
  birthday?: string | null
  notes?: string | null
  credit_limit_cents?: number
}
