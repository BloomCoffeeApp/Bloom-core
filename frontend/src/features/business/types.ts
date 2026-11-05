import type { ProFeature } from '@/features/license/api'

/** Mirrors backend `services/business_profile.py`. */
export type ModuleKey =
  | 'dine_in'
  | 'takeaway'
  | 'delivery'
  | 'tables'
  | 'orders'
  | 'stations'
  | 'barista'
  | 'stock'
  | 'purchases'
  | 'reports'
  | 'customers'
  | 'loyalty'
  | 'promos'
  | 'public_menu'

/** Known today; more can be added in the backend (unknown keys get a generic icon). */
export type ProfileKey = 'takeaway' | 'small' | 'salon' | 'delivery' | (string & {})

export type ModuleGroup = 'venta' | 'operacion' | 'gestion' | 'clientes'

export interface ModuleDef {
  key: ModuleKey
  label: string
  description: string
  group: ModuleGroup
  feature: ProFeature | null
  requires: ModuleKey[]
}

export interface ProfileDef {
  key: ProfileKey
  label: string
  description: string
  modules: Record<ModuleKey, boolean>
}

export interface BusinessCatalog {
  catalog: ModuleDef[]
  profiles: ProfileDef[]
}

export interface BusinessModules extends BusinessCatalog {
  profile: ProfileKey
  overrides: Partial<Record<ModuleKey, boolean>>
  modules: Record<ModuleKey, boolean>
}
