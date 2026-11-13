import type { Permission, Role } from '@/lib/auth'

export interface BusinessSettings {
  name: string
  /** Razón social (como figura en la inscripción); aparece en el comprobante. Opcional. */
  legal_name?: string
  cuit: string
  address: string
  phone: string
  ticket_footer: string
}

export interface LoyaltySettings {
  enabled: boolean
  pesos_per_point: number
  points_per_reward: number
  reward_value_cents: number
}

export interface AlertsSettings {
  expiry_days: number
  supplier_due_days: number
  roast_max_days: number
  roast_min_days: number
}

export interface NetworkSettings {
  lan_enabled: boolean
}

export interface BackupSettings {
  enabled: boolean
  keep: number
}

export interface PublicMenuSettings {
  enabled: boolean
  show_prices: boolean
  message: string
}

export interface AllSettings {
  business: BusinessSettings
  currency: string
  lock_minutes: number
  loyalty: LoyaltySettings
  alerts: AlertsSettings
  backup: BackupSettings
  network: NetworkSettings
  public_menu: PublicMenuSettings
  setup_done: boolean
}

export interface UserRow {
  id: number
  name: string
  role: Role
  role_name?: string | null
  color: string
  active: boolean
  last_login_at: string | null
  /** Free plan: this user can't log in. */
  locked?: boolean
}

export interface UserCreate {
  name: string
  pin: string
  role: Role
  color: string
}

export type UserUpdate = Partial<UserCreate> & { active?: boolean }

export interface PaymentMethod {
  id: number
  code: string
  name: string
  active: boolean
  surcharge_pct: number
}

export interface BackupRow {
  name: string
  size_bytes: number
  created_at: string
  label: string
}

export interface SystemInfo {
  app_name: string
  version: string
  data_dir: string
  db_path: string
  db_size_bytes: number
  backups_count: number
  last_backup: BackupRow | null
  lan_ips: string[]
  lan_url: string | null
  port: number
  lan_enabled: boolean
  lan_active: boolean
  network_public: boolean
}

export interface RestoreResult {
  ok: boolean
  restored: string
  safety_backup: string
  restart_required: boolean
  message: string
}

export interface AuditRow {
  id: number
  ts: string
  user_id: number | null
  user_name: string | null
  action: string
  entity: string
  entity_id: number | null
  payload: Record<string, unknown> | null
}

/** Mirrors backend services/roles.py `catalog()`. */
export interface PermissionInfo {
  key: Permission
  group: string
  label: string
  description: string
  /** Permission this one needs (added automatically). */
  requires: Permission | null
}

/** Mirrors backend services/roles.py `list_roles()`. */
export interface RoleRow {
  key: string
  name: string
  hint: string | null
  builtin: boolean
  /** False only for the admin role (always full access). */
  editable: boolean
  /** Built-in role whose permissions differ from the defaults. */
  customized: boolean
  permissions: Permission[]
  /** Active users with this role. */
  users: number
}
