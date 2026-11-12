import type { SaleDetail, SaleIn } from '../sales/types'

/** Mirrors backend services/collect.py (Pro `payments`). */
export type ChargeStatus = 'pending' | 'approved' | 'rejected' | 'cancelled' | 'expired' | 'refunded'
export type ChargeKind = 'qr' | 'link' | 'point' | 'transfer'
/** POS payment methods that open a charge instead of registering the sale right away. */
export type CollectMethod = 'mp_qr' | 'mp_point' | 'transferencia'

export interface TransferInfo {
  enabled: boolean
  alias: string
  cbu: string
  holder: string
  bank: string
  cuit: string
}

export interface CollectStatus {
  licensed: boolean
  provider: string | null
  provider_label: string | null
  connected: boolean
  account: MpAccount | Record<string, never>
  providers: { name: string; label: string }[]
  fake_allowed: boolean
  methods: CollectMethod[]
  transfer: TransferInfo
  expires_minutes: number
  point_device_id: string | null
  point_device_name: string | null
  default_screen_id: number | null
  screens: { id: number; name: string }[]
}

/** Pro Mercado Pago connection (bloom_pro mp_collect.info). */
export interface MpAccount {
  connected: boolean
  user_id?: number | null
  nickname?: string | null
  source?: 'oauth' | 'manual'
  live_mode?: boolean | null
  external_pos_id?: string | null
  store_name?: string | null
  needs_pos?: boolean
  expires_at?: number | null
  error?: string
}

export interface ChargeItem {
  name: string
  qty: number
  total_cents: number
}

export interface Charge {
  id: number
  status: ChargeStatus
  status_detail: string | null
  kind: ChargeKind
  provider: string
  amount_cents: number
  refunded_cents: number
  description: string
  qr_data: string | null
  url: string | null
  device_id: string | null
  expires_at: string | null
  approved_at: string | null
  ref: string
  ref_type: string
  ref_id: number | null
  sale_id: number | null
  screen_id: number | null
  error: string | null
  items: ChargeItem[]
  created_at: string
  sale: SaleDetail | null
  qr_png: string | null
}

export interface PosChargeIn {
  sale: SaleIn
  method: CollectMethod
  screen_id: number | null
}

export interface CustomerScreen {
  id: number
  name: string
  token: string
  active: boolean
  last_seen_at: string | null
  path: string
  url: string | null
  qr_png: string | null
}

export interface SaleChargeInfo {
  charge: Omit<Charge, 'sale' | 'qr_png'> | null
  refunds: { id: number; amount_cents: number; reason: string | null; ts: string; user_id: number | null }[]
  refundable_cents: number
}

/** Public customer screen state (GET /api/public/customer-screen). */
export interface ScreenState {
  screen: string
  business_name: string
  state: 'idle' | 'pending' | 'approved' | 'cancelled' | 'expired' | 'rejected'
  charge: {
    id: number
    kind: ChargeKind
    amount_cents: number
    items: ChargeItem[]
    expires_at: string | null
    fake: boolean
    qr_png?: string
    transfer?: Omit<TransferInfo, 'enabled'>
  } | null
}
