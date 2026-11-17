import type { ComponentType, LazyExoticComponent } from 'react'

import type { PublicMenuSettings } from '@/features/settings/types'

type Lazy<P = object> = LazyExoticComponent<ComponentType<P>>

/**
 * Pro modules live in a private repo and are plugged in at build time (`@pro` resolves to
 * `src/pro/index.ts` when present, else to `src/pro-stub.ts`). The core only knows this shape.
 */
export interface ProModules {
  edition: 'free' | 'pro'
  Barista?: Lazy
  Purchases?: Lazy
  Reports?: Lazy
  PublicMenuApp?: Lazy
  PublicMenuSettings?: Lazy<{ initial: PublicMenuSettings }>
  /** Configuración → Mesas: tables, QR sheet and ordering-from-the-table limits (public_menu). */
  TablesSettings?: Lazy
  /** Orders screen: phones connected to each open table, approvals, «Liberar mesa» (public_menu). */
  TableSessionsPanel?: Lazy
  /** `/salon`: the floor map as its own screen, with «Crear mesas» when there are none (public_menu). */
  FloorPlanPage?: Lazy
  /** Checkout of a table's account: pick the waiter who served it (public_menu). */
  CheckoutWaiter?: Lazy<{ tabId: number; value: number | null; onChange: (employeeId: number | null) => void }>
  /** POS «Enviar a mesa»: leaves the cart's new lines on a table's account without charging (public_menu). */
  SendToTableDialog?: Lazy<SendToTableProps>
  /** «Cambiar de mesa»: passes an account or one order to another table (public_menu). */
  MoveTableDialog?: Lazy<{ target: MoveTarget | null; onClose: () => void }>
  /** Configuración → Pedidos: stations and pickup screen (orders_pro). */
  OrdersStationsSettings?: Lazy
  /** Configuración → Pedidos online: take away / delivery from the online menu (online_orders). */
  OnlineOrdersSettings?: Lazy
  /** Productos → Promos: combos and scheduled discounts (promos). */
  PromosTab?: Lazy
  /** Configuración → Fidelización: stamp-card programs (loyalty_pro). */
  LoyaltyStampsSettings?: Lazy
  /** POS: the selected customer's stamp cards with one-tap redeem (loyalty_pro). */
  PosStampCards?: Lazy<PosStampCardsProps>
  /** Customer detail: stamp cards and their history (loyalty_pro). */
  CustomerStampCards?: Lazy<{ customerId: number }>
  /** Empleados: team, time entries, hours report and advances (staff). */
  Staff?: Lazy
  /** Login screen: "Fichar" button + PIN time clock. Renders nothing without staff or employees. */
  TimeClockButton?: Lazy
  /** User menu → Fichar: the same time clock, preselecting the logged-in user's employee. */
  TimeClockDialog?: Lazy<{ open: boolean; onOpenChange: (open: boolean) => void; userId?: number }>
  /** After login / before logout: «¿Fichar entrada / salida?» when the business turned it on (staff). */
  ClockPrompts?: Lazy<{ userId: number; logoutRequested: boolean; onLogoutProceed: () => void; onLogoutCancel: () => void }>
  /** `/equipo`: Bloom Equipo, the staff phone app (waiter first): login with the register's QR code, «Mis mesas» (public_menu). */
  TeamApp?: Lazy
  /** Configuración → Cobros: «Conectar Mercado Pago», the store/POS for the QR and the Point device (payments). */
  MercadoPagoConnect?: Lazy
}

/** A cart line as the backend takes it when an order is left on a table. */
export interface SendLine {
  product_id: number
  size_id: number | null
  qty: number
  modifier_ids: number[]
  notes: string | null
}

export interface SendToTableProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  lines: SendLine[]
  /** The table preselected (the cart is charging that table's account). */
  tableId?: number | null
  /** The order was left on the table: the POS empties what was sent. */
  onSent: (info: { table_label: string; order_id: number }) => void
}

/** What «Cambiar de mesa» moves: a whole account or one order. */
export type MoveTarget =
  | { kind: 'tab'; id: number; table_id: number; label: string }
  | { kind: 'order'; id: number; table_id: number | null; label: string; number?: number; prepaid?: boolean }

/** A stamp-card reward the POS adds to the cart. */
export type StampReward =
  | { kind: 'product'; program_id: number; label: string; product_id: number; size_id: number | null }
  | { kind: 'pct' | 'fixed'; program_id: number; label: string; value: number }

export interface PosStampCardsProps {
  customerId: number
  /** Programs already redeemed in the current cart (one reward per program per sale in the UI). */
  redeemed: number[]
  onRedeem: (reward: StampReward) => void
}
