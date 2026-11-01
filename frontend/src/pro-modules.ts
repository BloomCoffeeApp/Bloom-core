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
  /** Configuración → Pedidos: stations and pickup screen (orders_pro). */
  OrdersStationsSettings?: Lazy
}
