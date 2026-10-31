export interface Kpis {
  sales_cents: number
  tickets: number
  avg_ticket_cents: number
  gross_margin_cents: number | null
  margin_pct: number | null
}

export interface HourPoint {
  hour: number
  label: string
  sales_cents: number
  avg_cents: number
}

export interface DayPoint {
  date: string
  label: string
  tickets: number
  sales_cents: number
}

export interface TopProduct {
  product_id: number | null
  name: string
  qty: number
  sales_cents: number
}

export interface MixRow {
  key: string
  label: string
  sales_cents: number
  pct: number
}

export interface RecentSale {
  id: number
  number: number
  ts: string
  total_cents: number
  status: string
  channel: string
  user_name: string | null
  items_count: number
  payment_methods: string[]
}

export interface Dashboard {
  from: string
  to: string
  days: number
  show_costs: boolean
  compare_from: string
  compare_to: string
  compare_label: string
  kpis: Kpis
  previous: Kpis
  deltas: {
    sales_cents: number | null
    tickets: number | null
    avg_ticket_cents: number | null
    gross_margin_cents: number | null
  }
  hourly: HourPoint[]
  hourly_mode: 'day' | 'avg'
  daily: DayPoint[]
  top_products: TopProduct[]
  payment_mix: MixRow[]
  category_mix: MixRow[]
  channel_mix: MixRow[]
  recent_sales: RecentSale[]
}

/* ---- Contracts from other modules (tolerant: every field optional) ---- */

export interface OpenAlert {
  id: number
  type?: string
  severity?: 'info' | 'warning' | 'critical'
  title: string
  message?: string | null
  link?: string | null
  created_at?: string
}

export interface BaristaToday {
  current_espresso?: {
    recipe?: {
      name?: string
      dose_g?: number
      yield_g?: number
      time_min_s?: number
      time_max_s?: number
      temp_c?: number | null
      grind_ref?: string | null
    } | null
    coffee?: { name?: string; days_off_roast?: number | null; window?: string | null } | null
    last_dialed_shot?: { grind_setting?: string | number | null; time_s?: number; ts?: string } | null
  } | null
  shots_today?: number
  avg_time_today?: number | null
  maintenance_due?: { id: number; name: string; equipment_name?: string }[]
}

/** /cash/current may evolve; read defensively. */
export interface CashCurrent {
  id?: number
  opened_at?: string
  opening_cents?: number
  opened_by_name?: string
  sales_cents?: number
  total_sales_cents?: number
  tickets?: number
  expected_cash_cents?: number
  [k: string]: unknown
}
