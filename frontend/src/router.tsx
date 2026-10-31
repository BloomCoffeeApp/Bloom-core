import { Coffee } from 'lucide-react'
import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router'

import { AppShell } from '@/components/app-shell'
import { EmptyState } from '@/components/empty-state'
import { ProModule } from '@/features/license/pro-gate'
import { proModules as pro } from '@pro'
import { TourProvider } from '@/features/tutorial/tour'
import { type Role, useAuth } from '@/lib/auth'

// Each feature module owns its sub-routes (default export renders its own <Routes>).
const Dashboard = lazy(() => import('@/features/dashboard'))
const Pos = lazy(() => import('@/features/pos'))
const Cash = lazy(() => import('@/features/cash'))
const Sales = lazy(() => import('@/features/sales'))
const Catalog = lazy(() => import('@/features/catalog'))
const Stock = lazy(() => import('@/features/stock'))
const Customers = lazy(() => import('@/features/customers'))
const Alerts = lazy(() => import('@/features/alerts'))
const SettingsPage = lazy(() => import('@/features/settings'))

function Loading() {
  return (
    <div className="flex h-[60vh] items-center justify-center">
      <Coffee className="size-8 animate-pulse text-primary" />
    </div>
  )
}

function Guard({ roles, children }: { roles: Role[]; children: React.ReactNode }) {
  const { can } = useAuth()
  if (roles.length && !can(...roles))
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
          <Route path="pos/*" element={<Guard roles={['cajero', 'encargado']}><Pos /></Guard>} />
          <Route path="caja/*" element={<Guard roles={['cajero', 'encargado']}><Cash /></Guard>} />
          <Route path="ventas/*" element={<Guard roles={['cajero', 'encargado']}><Sales /></Guard>} />
          <Route path="barista/*" element={<Guard roles={['barista', 'encargado']}><ProModule feature="barista" component={pro.Barista} /></Guard>} />
          <Route path="productos/*" element={<Guard roles={['encargado']}><Catalog /></Guard>} />
          <Route path="stock/*" element={<Guard roles={['encargado', 'barista']}><Stock /></Guard>} />
          <Route path="compras/*" element={<Guard roles={['encargado']}><ProModule feature="purchases" component={pro.Purchases} /></Guard>} />
          <Route path="clientes/*" element={<Guard roles={['cajero', 'encargado']}><Customers /></Guard>} />
          <Route path="reportes/*" element={<Guard roles={['encargado']}><ProModule feature="reports" component={pro.Reports} /></Guard>} />
          <Route path="avisos/*" element={<Alerts />} />
          <Route path="config/*" element={<SettingsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </Suspense>
  )
}
