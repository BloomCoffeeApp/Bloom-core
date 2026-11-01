// Mirrors backend/app/schemas/orders.py (order screen, open tabs, metrics).
import type { Channel } from '../sales/types'

export type OrderStatus = 'pending' | 'received' | 'preparing' | 'ready' | 'delivered' | 'cancelled'
export type Level = 'pending' | 'ok' | 'warn' | 'late'

export interface OrdersSettings {
  enabled: boolean
  channels: Record<Channel, boolean>
  /** Target minutes per channel. */
  targets: Record<Channel, number>
  /** Yellow from this % of the target. */
  warn_pct: number
}

export interface OrderItem {
  id: number
  product_id: number | null
  name: string
  size_name: string | null
  qty: number
  modifiers: string[]
  notes: string | null
}

export interface Order {
  id: number
  /** Per local day; stations share the number of the same sale. */
  number: number
  source: 'pos' | 'table'
  status: OrderStatus
  channel: Channel
  table_id: number | null
  table_label: string | null
  station_id: number | null
  sale_id: number | null
  sale_number: number | null
  note: string | null
  target_minutes: number
  created_at: string
  received_at: string | null
  started_at: string | null
  ready_at: string | null
  prepared_by_name: string | null
  items: OrderItem[]
  /** Server-computed at `server_time` (the clock stops when ready). */
  elapsed_s: number
  late: boolean
  level: Level
}

export interface WaiterCall {
  id: number
  table_id: number
  table_label: string
  kind: 'waiter' | 'bill'
  created_at: string
  elapsed_s: number
}

export interface StationRef {
  id: number
  name: string
  print_tickets: boolean
}

export interface Board {
  server_time: string
  settings: OrdersSettings
  /** License includes `orders_pro` (stations, per-product targets, pickup screen). */
  pro: boolean
  stations: StationRef[]
  orders: Order[]
  calls: WaiterCall[]
  late_count: number
}

export interface TabLine {
  product_id: number | null
  name: string
  size_id: number | null
  size_name: string | null
  qty: number
  modifier_ids: number[]
  modifiers: string[]
  notes: string | null
  unit_price_cents: number
}

/** An open table ("mesa abierta"): confirmed orders waiting to be charged. */
export interface Tab {
  id: number
  table_id: number
  table_label: string
  opened_at: string
  orders: number
  unfinished: number
  lines: TabLine[]
  total_cents: number
}

export interface OrdersSummary {
  orders: number
  avg_prep_s: number | null
  late: number
  late_pct: number | null
  open: number
  open_late: number
}

export const STATUS_LABEL: Record<OrderStatus, string> = {
  pending: 'Por confirmar',
  received: 'Nuevo',
  preparing: 'En preparación',
  ready: 'Listo',
  delivered: 'Entregado',
  cancelled: 'Cancelado',
}
