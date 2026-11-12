/** Mirrors backend app/schemas/expenses.py. Money in integer cents; dates "YYYY-MM-DD"; months "YYYY-MM". */
export type ExpenseKind = 'fixed' | 'variable'
export type ExpenseStatus = 'paid' | 'pending'

export interface ExpenseCategory {
  id: number
  name: string
  kind: ExpenseKind
  active: boolean
  sort_order: number
}

export interface Expense {
  id: number
  category_id: number
  category_name: string
  kind: ExpenseKind
  description: string
  amount_cents: number
  date: string
  due_date: string | null
  status: ExpenseStatus
  overdue: boolean
  paid_at: string | null
  payment_method: string | null
  payment_method_name: string | null
  /** Paid with money taken from the open cash drawer (an "egreso" was recorded). */
  from_cash: boolean
  recurring_id: number | null
  period: string | null
  has_receipt: boolean
  notes: string | null
  created_at: string
}

export interface ExpenseInput {
  category_id: number
  kind?: ExpenseKind
  description: string
  amount_cents: number
  date?: string
  status: ExpenseStatus
  due_date?: string | null
  payment_method?: string | null
  from_cash?: boolean
  notes?: string | null
}

export interface CategoryTotal {
  category_id: number
  name: string
  count: number
  total_cents: number
  pct: number
}

export interface ExpenseList {
  period: string
  items: Expense[]
  totals: {
    total_cents: number
    paid_cents: number
    pending_cents: number
    overdue_cents: number
    fixed_cents: number
    variable_cents: number
    count: number
  }
  by_category: CategoryTotal[]
}

export interface RecurringExpense {
  id: number
  category_id: number
  category_name: string
  description: string
  amount_cents: number
  day_of_month: number
  payment_method: string | null
  payment_method_name: string | null
  active: boolean
  start_period: string
  last_period: string | null
  notes: string | null
}

export interface RecurringInput {
  category_id: number
  description: string
  amount_cents: number
  day_of_month: number
  payment_method?: string | null
  start_period?: string
  notes?: string | null
}

/** Ventas − costo de mercadería − cortesías/mermas − gastos = ganancia real. */
export interface PeriodResult {
  from: string
  to: string
  period?: string
  partial?: boolean
  sales_cents: number
  tickets: number
  cogs_cents: number
  gross_margin_cents: number
  waste_cents: number
  courtesy_cost_cents: number
  losses_cents: number
  expenses_cents: number
  expenses_pending_cents: number
  /** Current month: expenses dated after today (not in the result "so far"). */
  expenses_upcoming_cents?: number
  profit_cents: number
  profit_pct: number | null
}

export interface MonthResult {
  period: string
  partial: boolean
  current: PeriodResult
  previous: PeriodResult & { period: string }
}
