import {
  BarChart3,
  Bell,
  Boxes,
  ClipboardList,
  Coffee,
  LayoutDashboard,
  type LucideIcon,
  Package,
  Settings,
  ShoppingBag,
  ShoppingCart,
  Truck,
  Users,
  Wallet,
} from 'lucide-react'

import type { ProFeature } from '@/features/license/api'
import type { Role } from '@/lib/auth'

export interface NavItem {
  to: string
  label: string
  icon: LucideIcon
  /** Roles allowed besides admin. Empty = everyone. */
  roles: Role[]
  group: 'operacion' | 'gestion' | 'sistema'
  shortcut?: string
  /** Pro module: shows a Pro badge when the license doesn't include it. */
  feature?: ProFeature
}

export const NAV: NavItem[] = [
  { to: '/', label: 'Inicio', icon: LayoutDashboard, roles: [], group: 'operacion' },
  { to: '/pos', label: 'Punto de venta', icon: ShoppingCart, roles: ['cajero', 'encargado'], group: 'operacion', shortcut: 'F1' },
  { to: '/pedidos', label: 'Pedidos', icon: ClipboardList, roles: [], group: 'operacion' },
  { to: '/caja', label: 'Caja', icon: Wallet, roles: ['cajero', 'encargado'], group: 'operacion' },
  { to: '/barista', label: 'Barista', icon: Coffee, roles: ['barista', 'encargado'], group: 'operacion', feature: 'barista' },
  { to: '/productos', label: 'Productos', icon: Package, roles: ['encargado'], group: 'gestion' },
  { to: '/stock', label: 'Stock', icon: Boxes, roles: ['encargado', 'barista'], group: 'gestion' },
  { to: '/compras', label: 'Compras', icon: Truck, roles: ['encargado'], group: 'gestion', feature: 'purchases' },
  { to: '/clientes', label: 'Clientes', icon: Users, roles: ['cajero', 'encargado'], group: 'gestion' },
  { to: '/ventas', label: 'Ventas', icon: ShoppingBag, roles: ['cajero', 'encargado'], group: 'gestion' },
  { to: '/reportes', label: 'Reportes', icon: BarChart3, roles: ['encargado'], group: 'gestion', feature: 'reports' },
  { to: '/avisos', label: 'Avisos y alertas', icon: Bell, roles: [], group: 'sistema' },
  { to: '/config', label: 'Configuración', icon: Settings, roles: [], group: 'sistema' },
]

export const NAV_GROUPS: Record<NavItem['group'], string> = {
  operacion: 'Operación',
  gestion: 'Gestión',
  sistema: 'Sistema',
}
