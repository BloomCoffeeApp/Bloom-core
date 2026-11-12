import { Coffee } from 'lucide-react'
import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router'

import { AppShell } from '@/components/app-shell'
import { EmptyState } from '@/components/empty-state'
import { ModuleRoute } from '@/features/business/module-route'
import { ProModule } from '@/features/license/pro-gate'
import { proModules as pro } from '@pro'
import { TourProvider } from '@/features/tutorial/tour'
import { type Permission, useAuth } from '@/lib/auth'

// Each feature module owns its sub-routes (default export renders its own <Routes>).
const Dashboard = lazy(() => import('@/features/dashboard'))
const Pos = lazy(() => import('@/features/pos'))
const Cash = lazy(() => import('@/features/cash'))
const Orders = lazy(() => import('@/features/orders'))
const Sales = lazy(() => import('@/features/sales'))
const Catalog = lazy(() => import('@/features/catalog'))
const Stock = lazy(() => import('@/features/stock'))
const Customers = lazy(() => import('@/features/customers'))
const Alerts = lazy(() => import('@/features/alerts'))
const Expenses = lazy(() => import('@/features/expenses'))
const SettingsPage = lazy(() => import('@/features/settings'))

function Loading() {
  return (
    <div className="flex h-[60vh] items-center justify-center">
      <Coffee className="size-8 animate-pulse text-primary" />
    </div>
  )
}

function Guard({ perms, children }: { perms: Permission[]; children: React.ReactNode }) {
  const { can } = useAuth()
  if (perms.length && !can(...perms))
    return <EmptyState title="Sin acceso" description="Tu usuario no tiene permiso para ver esta sección." />
  return <>{children}</>
}

export function AppRoutes() {
  return (
    <Suspense fallback={<Loading />}>
      <Routes>
        <Route
          element={
            <TourProvider>
              <AppShell />
            </TourProvider>
          }
        >
          <Route index element={<Dashboard />} />
          <Route path="pos/*" element={<Guard perms={['pos.sell']}><Pos /></Guard>} />
          <Route path="pedidos/*" element={<ModuleRoute module="orders"><Orders /></ModuleRoute>} />
          <Route path="caja/*" element={<Guard perms={['cash.open_close', 'cash.movements']}><Cash /></Guard>} />
          <Route path="ventas/*" element={<Guard perms={['pos.sell']}><Sales /></Guard>} />
          <Route path="barista/*" element={<Guard perms={['barista.use']}><ModuleRoute module="barista"><ProModule feature="barista" component={pro.Barista} /></ModuleRoute></Guard>} />
          <Route path="productos/*" element={<Guard perms={['catalog.edit', 'prices.edit']}><Catalog /></Guard>} />
          <Route path="stock/*" element={<Guard perms={['stock.view']}><ModuleRoute module="stock"><Stock /></ModuleRoute></Guard>} />
          <Route path="compras/*" element={<Guard perms={['purchases.manage']}><ModuleRoute module="purchases"><ProModule feature="purchases" component={pro.Purchases} /></ModuleRoute></Guard>} />
          <Route path="clientes/*" element={<Guard perms={['customers.edit']}><ModuleRoute module="customers"><Customers /></ModuleRoute></Guard>} />
          <Route path="gastos/*" element={<Guard perms={['expenses.manage']}><Expenses /></Guard>} />
          <Route path="reportes/*" element={<Guard perms={['reports.view']}><ModuleRoute module="reports"><ProModule feature="reports" component={pro.Reports} /></ModuleRoute></Guard>} />
          <Route path="empleados/*" element={<Guard perms={['staff.manage']}><ProModule feature="staff" component={pro.Staff} /></Guard>} />
          <Route path="avisos/*" element={<Alerts />} />
          <Route path="config/*" element={<SettingsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </Suspense>
  )
}
