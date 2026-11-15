import {
  Banknote,
  Bell,
  Building2,
  ClipboardList,
  CreditCard,
  Gift,
  HardDrive,
  Info,
  KeyRound,
  LayoutGrid,
  Lock,
  Mail,
  type LucideIcon,
  Palette,
  Printer,
  QrCode,
  ShieldCheck,
  ShoppingBag,
  Sparkles,
  UserRound,
  Users,
  Wifi,
} from 'lucide-react'
import { type ReactNode, Suspense } from 'react'
import { Route, Routes, useSearchParams } from 'react-router'

import { PageHeader } from '@/components/page-header'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { type Permission, useAuth } from '@/lib/auth'

import { usePaymentMethods, useSettings } from './api'
import { CardSkeleton } from './form'
import { AlertsSection, AppearanceSection, BusinessSection, LoyaltySection, SecuritySection, TipsSection } from './general-sections'
import { AccountSection } from '../account/account-section'
import { NotificationsSection } from '../account/notifications-section'
import { LicenseSection } from '../license/license-section'
import { FreeActivesSection } from '../license/free-actives-section'
import { UpgradeCard } from '../license/pro-gate'
import { useFreePlan, useHasFeature } from '../license/api'
import { proModules } from '@pro'
import { AboutSection, BackupSection, NetworkSection, PaymentMethodsSection } from './system-sections'
import { RolesSection } from './roles-section'
import { UsersSection } from './users-section'
import { OrdersSettingsSection } from '../orders/settings-section'
import { PrintersSection } from '../printing/settings-section'
import { CollectSettingsSection } from '../collect/settings-section'
import { useModules } from '../business/api'
import { BusinessProfileSection } from '../business/profile-section'
import type { ModuleKey } from '../business/types'

interface TabDef {
  value: string
  label: string
  icon: LucideIcon
  render: () => ReactNode
  /** Hidden when the business type doesn't use this module. */
  module?: ModuleKey
  /** Who sees it: a permission, or 'admin' for owner-only tabs. */
  perm?: Permission | 'admin'
}

function SettingsPage() {
  const { can } = useAuth()
  const isAdmin = can()
  const settings = useSettings()
  const payments = usePaymentMethods(can('settings.manage'))
  const [params, setParams] = useSearchParams()
  const s = settings.data
  const lanPro = useHasFeature('lan')
  const menuPro = useHasFeature('public_menu')
  const onlinePro = useHasFeature('online_orders')
  const ordersPro = useHasFeature('orders_pro')
  const stampsPro = useHasFeature('loyalty_pro')
  const modules = useModules()
  const freePlan = useFreePlan()

  const withSettings = (fn: () => ReactNode) => () => (s ? fn() : <CardSkeleton />)

  const adminTabs: TabDef[] = (
    [
        { value: 'negocio', perm: 'settings.manage', label: 'Negocio', icon: Building2, render: withSettings(() => (
          <div className="space-y-6">
            <BusinessSection initial={s!.business} />
            <TipsSection initial={s!.tips} />
            <BusinessProfileSection />
          </div>
        )) },
        { value: 'licencia', perm: 'admin', label: 'Licencia', icon: Sparkles, render: () => <LicenseSection /> },
        { value: 'activos', perm: 'admin', label: freePlan.data && !freePlan.data.limited ? 'Plan gratuito' : 'Elegí tus activos', icon: Lock, render: () => <FreeActivesSection /> },
        { value: 'cuenta', perm: 'admin', label: 'Cuenta', icon: UserRound, render: () => <AccountSection /> },
        { value: 'notificaciones', perm: 'admin', label: 'Notificaciones', icon: Mail, render: () => <NotificationsSection /> },
        { value: 'usuarios', perm: 'users.manage', label: 'Usuarios', icon: Users, render: () => <UsersSection /> },
        { value: 'roles', perm: 'admin', label: 'Roles y permisos', icon: KeyRound, render: () => <RolesSection /> },
        ...(payments.isSuccess
          ? [{ value: 'pagos', perm: 'settings.manage', label: 'Medios de pago', icon: CreditCard, render: () => <PaymentMethodsSection query={payments} /> }]
          : []),
        { value: 'cobros', label: 'Cobros', icon: Banknote, render: () => <CollectSettingsSection /> },
        { value: 'fidelizacion', perm: 'settings.manage', label: 'Fidelización', icon: Gift, module: 'loyalty', render: withSettings(() => (
          <div className="space-y-6">
            <LoyaltySection initial={s!.loyalty} />
            {!proModules.LoyaltyStampsSettings ? (
              <UpgradeCard feature="loyalty_pro" compact notIncluded />
            ) : stampsPro === false ? (
              <UpgradeCard feature="loyalty_pro" compact />
            ) : (
              <Suspense fallback={<CardSkeleton />}>
                <proModules.LoyaltyStampsSettings />
              </Suspense>
            )}
          </div>
        )) },
        { value: 'alertas', perm: 'settings.manage', label: 'Alertas', icon: Bell, render: withSettings(() => <AlertsSection initial={s!.alerts} />) },
        { value: 'seguridad', perm: 'settings.manage', label: 'Seguridad', icon: ShieldCheck, render: withSettings(() => <SecuritySection initial={s!.lock_minutes} />) },
        { value: 'respaldo', perm: 'system.manage', label: 'Respaldo', icon: HardDrive, render: withSettings(() => <BackupSection settings={s!.backup} />) },
        { value: 'red', perm: 'settings.manage', label: 'Red local', icon: Wifi, render: withSettings(() =>
          lanPro === false ? <UpgradeCard feature="lan" compact /> : <NetworkSection initialEnabled={!!s!.network?.lan_enabled} />,
        ) },
        { value: 'impresoras', perm: 'settings.manage', label: 'Impresoras', icon: Printer, render: () => <PrintersSection /> },
        { value: 'pedidos', perm: 'settings.manage', label: 'Pedidos', icon: ClipboardList, module: 'orders', render: () => (
          <div className="space-y-6">
            <OrdersSettingsSection />
            {!modules.on('stations') ? null : !proModules.OrdersStationsSettings ? (
              <UpgradeCard feature="orders_pro" compact notIncluded />
            ) : ordersPro === false ? (
              <UpgradeCard feature="orders_pro" compact />
            ) : (
              <Suspense fallback={<CardSkeleton />}>
                <proModules.OrdersStationsSettings />
              </Suspense>
            )}
          </div>
        ) },
        { value: 'mesas', perm: 'settings.manage', label: 'Mesas y pedidos QR', icon: LayoutGrid, module: 'tables', render: () =>
          !proModules.TablesSettings ? (
            <UpgradeCard feature="public_menu" compact notIncluded />
          ) : menuPro === false ? (
            <UpgradeCard feature="public_menu" compact />
          ) : (
            <Suspense fallback={<CardSkeleton />}>
              <proModules.TablesSettings />
            </Suspense>
          ),
        },
        { value: 'pedidos-online', perm: 'orders.manage', label: 'Pedidos online', icon: ShoppingBag, render: () =>
          !proModules.OnlineOrdersSettings ? (
            <UpgradeCard feature="online_orders" compact notIncluded />
          ) : onlinePro === false ? (
            <UpgradeCard feature="online_orders" compact />
          ) : (
            <Suspense fallback={<CardSkeleton />}>
              <proModules.OnlineOrdersSettings />
            </Suspense>
          ),
        },
        { value: 'menu-clientes', perm: 'settings.manage', label: 'Menú para clientes', icon: QrCode, module: 'public_menu', render: withSettings(() =>
          !proModules.PublicMenuSettings ? (
            <UpgradeCard feature="public_menu" compact notIncluded />
          ) : menuPro === false ? (
            <UpgradeCard feature="public_menu" compact />
          ) : (
            <Suspense fallback={<CardSkeleton />}>
              <proModules.PublicMenuSettings initial={s!.public_menu} />
            </Suspense>
          ),
        ) },
    ] as TabDef[]
  ).filter((t) => !t.perm || (t.perm === 'admin' ? isAdmin : can(t.perm)))
  const tabs: TabDef[] = [
    ...adminTabs,
    { value: 'apariencia', label: 'Apariencia', icon: Palette, render: () => <AppearanceSection /> },
    { value: 'acerca', label: 'Acerca de', icon: Info, render: () => <AboutSection isAdmin={can('system.manage')} /> },
  ].filter((t: TabDef) => !t.module || modules.on(t.module))
  const requested = params.get('tab')
  const current = tabs.some((t) => t.value === requested) ? requested! : tabs[0].value

  return (
    <div>
      <PageHeader
        title="Configuración"
        description={adminTabs.length ? 'Datos del negocio, usuarios, respaldos y preferencias.' : 'Preferencias de este equipo.'}
      />
      <Tabs
        value={current}
        onValueChange={(v) => setParams({ tab: v }, { replace: true })}
        orientation="vertical"
        className="flex flex-col gap-6 lg:flex-row lg:items-start"
      >
        <TabsList className="h-auto! w-full flex-row flex-wrap justify-start gap-1 bg-card p-1.5 lg:sticky lg:top-4 lg:w-56 lg:shrink-0 lg:flex-col lg:items-stretch lg:rounded-2xl lg:border">
          {tabs.map(({ value, label, icon: Icon }) => (
            <TabsTrigger
              key={value}
              value={value}
              className="h-9 flex-none justify-start gap-2 px-3 data-active:bg-primary/10 data-active:text-primary lg:w-full"
            >
              <Icon />
              {label}
            </TabsTrigger>
          ))}
        </TabsList>
        <div className="min-w-0 flex-1">
          {tabs.map((t) => (
            <TabsContent key={t.value} value={t.value} className="mt-0">
              {t.render()}
            </TabsContent>
          ))}
        </div>
      </Tabs>
    </div>
  )
}

export default function Module() {
  return (
    <Routes>
      <Route path="*" element={<SettingsPage />} />
    </Routes>
  )
}
