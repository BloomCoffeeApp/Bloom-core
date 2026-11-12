import {
  BarChart3,
  Bell,
  Boxes,
  ClipboardList,
  Coffee,
  LayoutDashboard,
  type LucideIcon,
  Package,
  Receipt,
  Settings,
  ShoppingBag,
  ShoppingCart,
  Truck,
  UserRoundCheck,
  Users,
  Wallet,
} from 'lucide-react'

import type { ModuleKey } from '@/features/business/types'
import type { ProFeature } from '@/features/license/api'
import type { Permission } from '@/lib/permissions'

export interface NavItem {
  to: string
  label: string
  icon: LucideIcon
  /** Permissions that show it (any of them; admin always). Empty = everyone. */
  perms: Permission[]
  group: 'operacion' | 'gestion' | 'sistema'
  shortcut?: string
  /** Pro module: shows a Pro badge when the license doesn't include it. */
  feature?: ProFeature
  /** Hidden when the business type (profile) doesn't use this module. */
  module?: ModuleKey
}

export const NAV: NavItem[] = [
  { to: '/', label: 'Inicio', icon: LayoutDashboard, perms: [], group: 'operacion' },
  { to: '/pos', label: 'Punto de venta', icon: ShoppingCart, perms: ['pos.sell'], group: 'operacion', shortcut: 'F1' },
  { to: '/pedidos', label: 'Pedidos', icon: ClipboardList, perms: [], group: 'operacion', module: 'orders' },
  { to: '/caja', label: 'Caja', icon: Wallet, perms: ['cash.open_close', 'cash.movements'], group: 'operacion' },
  { to: '/barista', label: 'Barista', icon: Coffee, perms: ['barista.use'], group: 'operacion', feature: 'barista', module: 'barista' },
  { to: '/productos', label: 'Productos', icon: Package, perms: ['catalog.edit', 'prices.edit'], group: 'gestion' },
  { to: '/stock', label: 'Stock', icon: Boxes, perms: ['stock.view'], group: 'gestion', module: 'stock' },
  { to: '/compras', label: 'Compras', icon: Truck, perms: ['purchases.manage'], group: 'gestion', feature: 'purchases', module: 'purchases' },
  { to: '/clientes', label: 'Clientes', icon: Users, perms: ['customers.edit'], group: 'gestion', module: 'customers' },
  { to: '/ventas', label: 'Ventas', icon: ShoppingBag, perms: ['pos.sell'], group: 'gestion' },
  { to: '/gastos', label: 'Gastos', icon: Receipt, perms: ['expenses.manage'], group: 'gestion' },
  { to: '/reportes', label: 'Reportes', icon: BarChart3, perms: ['reports.view'], group: 'gestion', feature: 'reports', module: 'reports' },
  { to: '/empleados', label: 'Empleados', icon: UserRoundCheck, perms: ['staff.manage'], group: 'gestion', feature: 'staff' },
  { to: '/avisos', label: 'Avisos y alertas', icon: Bell, perms: [], group: 'sistema' },
  { to: '/config', label: 'Configuración', icon: Settings, perms: [], group: 'sistema' },
]

export const NAV_GROUPS: Record<NavItem['group'], string> = {
  operacion: 'Operación',
  gestion: 'Gestión',
  sistema: 'Sistema',
}
