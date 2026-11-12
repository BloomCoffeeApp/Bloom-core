// Mirrors backend/app/schemas/orders.py (order screen, open tabs, metrics).
import type { Channel } from '../sales/types'

export type OrderStatus =
  | 'pending'
  | 'received'
  | 'accepted'
  | 'awaiting_pay'
  | 'paid'
  | 'preparing'
  | 'ready'
  | 'dispatched'
  | 'delivered'
  | 'cancelled'
  | 'rejected'
  | 'expired'
/** Each channel's flow (backend services/order_flows.py). */
export type FlowKey = 'caja' | 'mesa' | 'take_away' | 'delivery'
export type BoardColumn = 'confirm' | 'payment' | 'queue' | 'preparing' | 'ready' | 'done'

/** A button of the order's current state, rendered from data. */
export interface OrderAction {
  to: OrderStatus
  label: string
  tone: 'primary' | 'success' | 'secondary' | 'outline' | 'danger'
  place: 'main' | 'menu'
  /** eta = accept dialog; reason = required reason; reason_optional; confirm. */
  needs: 'eta' | 'reason' | 'reason_optional' | 'confirm' | null
  icon: string | null
}

export interface CustomerChange {
  field: string
  label: string
  saved: string | null
  new: string | null
}

/** Take away / delivery from the online menu (Pro online_orders). */
export interface OnlineInfo {
  customer_id: number | null
  customer_name: string | null
  customer_phone: string | null
  address: string | null
  address_ref: string | null
  delivery_zone: string | null
  delivery_fee_cents: number
  total_cents: number
  payment_method: 'online' | 'transfer' | 'cash' | null
  payment_url: string | null
  charge_id: number | null
  refunded_cents: number
  eta_minutes: number | null
  accepted_at: string | null
  paid_at: string | null
  expires_at: string | null
  expires_in_s: number | null
  tracking_url: string | null
  cancel_reason: string | null
  sale_registered: boolean
  customer_changes: CustomerChange[]
}
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
  source: 'pos' | 'table' | 'online'
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
  flow: FlowKey
  /** The step's name in this order's flow ("Servido", "Retirado", "Cancelado · devuelto"…). */
  status_label: string
  column: BoardColumn
  /** Buttons of the current state (backend order_flows), already filtered by its guards. */
  actions: OrderAction[]
  payment_status: 'unpaid' | 'pending' | 'paid' | 'refunded' | 'refund_due'
  online: OnlineInfo | null
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
  /** Its kitchen tickets go straight to a thermal printer (the backend prints them). */
  direct_print?: boolean
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
  /** Kitchen tickets the thermal printer couldn't print: this screen prints them with the dialog. */
  print_failures?: { order_id: number; error: string }[]
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
  accepted: 'Aceptado',
  awaiting_pay: 'Pago pendiente',
  paid: 'Pagado',
  preparing: 'En preparación',
  ready: 'Listo',
  dispatched: 'Enviado',
  delivered: 'Entregado',
  cancelled: 'Cancelado',
  rejected: 'Rechazado',
  expired: 'Vencido',
}
