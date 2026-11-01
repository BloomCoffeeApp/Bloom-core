import {
  Bell,
  Building2,
  ClipboardList,
  CreditCard,
  Gift,
  HardDrive,
  Info,
  LayoutGrid,
  Mail,
  type LucideIcon,
  Palette,
  QrCode,
  ShieldCheck,
  Sparkles,
  UserRound,
  Users,
  Wifi,
} from 'lucide-react'
import { type ReactNode, Suspense } from 'react'
import { Route, Routes, useSearchParams } from 'react-router'

import { PageHeader } from '@/components/page-header'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useAuth } from '@/lib/auth'

import { usePaymentMethods, useSettings } from './api'
import { CardSkeleton } from './form'
import { AlertsSection, AppearanceSection, BusinessSection, LoyaltySection, SecuritySection } from './general-sections'
import { AccountSection } from '../account/account-section'
import { NotificationsSection } from '../account/notifications-section'
import { LicenseSection } from '../license/license-section'
import { UpgradeCard } from '../license/pro-gate'
import { useHasFeature } from '../license/api'
import { proModules } from '@pro'
import { AboutSection, BackupSection, NetworkSection, PaymentMethodsSection } from './system-sections'
import { UsersSection } from './users-section'
import { OrdersSettingsSection } from '../orders/settings-section'

interface TabDef {
  value: string
  label: string
  icon: LucideIcon
  render: () => ReactNode
}

function SettingsPage() {
  const { can } = useAuth()
  const isAdmin = can()
  const settings = useSettings()
  const payments = usePaymentMethods(isAdmin)
  const [params, setParams] = useSearchParams()
  const s = settings.data
  const lanPro = useHasFeature('lan')
  const menuPro = useHasFeature('public_menu')
  const ordersPro = useHasFeature('orders_pro')

  const withSettings = (fn: () => ReactNode) => () => (s ? fn() : <CardSkeleton />)

  const adminTabs: TabDef[] = isAdmin
    ? [
        { value: 'negocio', label: 'Negocio', icon: Building2, render: withSettings(() => <BusinessSection initial={s!.business} />) },
        { value: 'licencia', label: 'Licencia', icon: Sparkles, render: () => <LicenseSection /> },
        { value: 'cuenta', label: 'Cuenta', icon: UserRound, render: () => <AccountSection /> },
        { value: 'notificaciones', label: 'Notificaciones', icon: Mail, render: () => <NotificationsSection /> },
        { value: 'usuarios', label: 'Usuarios', icon: Users, render: () => <UsersSection /> },
        ...(payments.isSuccess
          ? [{ value: 'pagos', label: 'Medios de pago', icon: CreditCard, render: () => <PaymentMethodsSection query={payments} /> }]
          : []),
        { value: 'fidelizacion', label: 'Fidelización', icon: Gift, render: withSettings(() => <LoyaltySection initial={s!.loyalty} />) },
        { value: 'alertas', label: 'Alertas', icon: Bell, render: withSettings(() => <AlertsSection initial={s!.alerts} />) },
        { value: 'seguridad', label: 'Seguridad', icon: ShieldCheck, render: withSettings(() => <SecuritySection initial={s!.lock_minutes} />) },
        { value: 'respaldo', label: 'Respaldo', icon: HardDrive, render: withSettings(() => <BackupSection settings={s!.backup} />) },
        { value: 'red', label: 'Red local', icon: Wifi, render: withSettings(() =>
          lanPro === false ? <UpgradeCard feature="lan" compact /> : <NetworkSection initialEnabled={!!s!.network?.lan_enabled} />,
        ) },
        { value: 'pedidos', label: 'Pedidos', icon: ClipboardList, render: () => (
          <div className="space-y-6">
            <OrdersSettingsSection />
            {!proModules.OrdersStationsSettings ? (
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
        { value: 'mesas', label: 'Mesas y pedidos QR', icon: LayoutGrid, render: () =>
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
        { value: 'menu-clientes', label: 'Menú para clientes', icon: QrCode, render: withSettings(() =>
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
      ]
    : []
  const tabs: TabDef[] = [
    ...adminTabs,
    { value: 'apariencia', label: 'Apariencia', icon: Palette, render: () => <AppearanceSection /> },
    { value: 'acerca', label: 'Acerca de', icon: Info, render: () => <AboutSection isAdmin={isAdmin} /> },
  ]
  const requested = params.get('tab')
  const current = tabs.some((t) => t.value === requested) ? requested! : tabs[0].value

  return (
    <div>
      <PageHeader
        title="Configuración"
        description={isAdmin ? 'Datos del negocio, usuarios, respaldos y preferencias.' : 'Preferencias de este equipo.'}
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
