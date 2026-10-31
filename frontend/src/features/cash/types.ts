// Mirrors backend/app/schemas/sales.py (cash section)

export interface CashMovement {
  id: number
  type: 'in' | 'out'
  amount_cents: number
  reason: string
  user_id: number | null
  user_name: string | null
  ts: string
}

export interface MethodTotal {
  method: string
  name: string
  sales_cents: number
  count: number
  expected_cents: number
  counted_cents: number | null
  difference_cents: number | null
}

export interface CategoryTotal {
  category_id: number | null
  name: string
  qty: number
  total_cents: number
}

export interface CashSession {
  id: number
  status: 'open' | 'closed'
  opened_at: string
  opened_by: number
  opened_by_name: string | null
  closed_at: string | null
  closed_by: number | null
  closed_by_name: string | null
  opening_cents: number
  notes: string | null
  sales_total_cents: number
  tickets: number
  avg_ticket_cents: number
  voided_count: number
  voided_total_cents: number
  /** Courtesies ("invita la casa"): $0 charged, not in totals; courtesy_cents = menu value given away. */
  courtesy_count: number
  courtesy_cents: number
  discounts_cents: number
  movements_in_cents: number
  movements_out_cents: number
  expected_cash_cents: number
  difference_cents: number | null
  by_method: MethodTotal[]
  movements: CashMovement[]
}

export interface CashSessionDetail extends CashSession {
  by_category: CategoryTotal[]
  business: { name?: string; address?: string; cuit?: string }
}

export interface CashSessionListItem {
  id: number
  status: 'open' | 'closed'
  opened_at: string
  closed_at: string | null
  opened_by_name: string | null
  closed_by_name: string | null
  opening_cents: number
  sales_total_cents: number
  tickets: number
  difference_cents: number | null
}
