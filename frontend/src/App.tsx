import { useQuery } from '@tanstack/react-query'
import { Coffee, RefreshCw, WifiOff } from 'lucide-react'
import { lazy, Suspense } from 'react'
import { BrowserRouter } from 'react-router'

import { Button } from '@/components/ui/button'
import { readApi } from '@/components/use-desktop'
import { DesktopTitleBar } from '@/components/window-controls'
import { LoginPage } from '@/features/auth/login-page'
import { SetupPage } from '@/features/auth/setup-page'
import { api } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { AppRoutes } from '@/router'
import { proModules } from '@pro'

interface SetupStatus {
  needs_setup: boolean
  business: { name: string }
}

// Customer-facing menu (QR / counter screen): public, no login required.
const isPublicMenuPath = () => /^\/menu(\/|$)/.test(window.location.pathname)
// Customer-facing payment screen (tablet/TV on the LAN, by its secret token): public too.
const CustomerScreen = lazy(() => import('@/features/collect/customer-screen'))
const isCustomerScreenPath = () => /^\/pantalla-cliente\/?$/.test(window.location.pathname)
// Staff phone app (Bloom Equipo, Pro): its own login behind the code in the register's QR.
const isTeamPath = () => /^\/equipo(\/|$)/.test(window.location.pathname)

function Splash() {
  return (
    <div className="flex min-h-svh items-center justify-center">
      <Coffee className="size-10 animate-pulse text-primary" />
    </div>
  )
}

export default function App() {
  if (isCustomerScreenPath())
    return (
      <Suspense fallback={<Splash />}>
        <CustomerScreen />
      </Suspense>
    )
  if (isTeamPath()) return <TeamRoute />
  const PublicMenuApp = proModules.PublicMenuApp
  if (PublicMenuApp && isPublicMenuPath())
    return (
      <Suspense fallback={<Splash />}>
        <BrowserRouter>
          <PublicMenuApp />
        </BrowserRouter>
      </Suspense>
    )
  return <PrivateApp />
}

function TeamRoute() {
  const TeamApp = proModules.TeamApp
  if (!TeamApp)
    return (
      <div className="flex min-h-svh flex-col items-center justify-center gap-3 p-6 text-center">
        <Coffee className="size-10 text-primary" />
        <h1 className="font-heading text-2xl font-semibold">Bloom Equipo</h1>
        <p className="max-w-sm text-muted-foreground">La app del equipo para celulares es parte de Bloom Pro.</p>
      </div>
    )
  return (
    <Suspense fallback={<Splash />}>
      <BrowserRouter>
        <TeamApp />
      </BrowserRouter>
    </Suspense>
  )
}

/** The app shell loaded (maybe from the installed app's cache) but the shop's PC doesn't answer. */
function OfflineScreen({ retrying, onRetry }: { retrying: boolean; onRetry: () => void }) {
  const desktop = !!readApi()
  return (
    <div className="flex min-h-svh flex-col items-center justify-center gap-4 p-6 text-center" role="alert">
      <span className="flex size-16 items-center justify-center rounded-full bg-muted">
        <WifiOff className="size-8 text-muted-foreground" />
      </span>
      <h1 className="font-heading text-2xl font-semibold">{desktop ? 'No se pudo iniciar la app' : 'Sin conexión con la PC del local'}</h1>
      <p className="max-w-md text-muted-foreground">
        {desktop
          ? 'El servidor interno no responde. Cerrá y volvé a abrir la aplicación.'
          : 'Revisá que la PC del local esté prendida, con la app abierta y el modo red local activado, y que este equipo esté conectado al mismo Wi-Fi.'}
      </p>
      <Button size="lg" className="h-12" onClick={onRetry} disabled={retrying}>
        <RefreshCw className={retrying ? 'animate-spin' : undefined} /> Reintentar
      </Button>
    </div>
  )
}

function PrivateApp() {
  const { user, loading } = useAuth()
  const status = useQuery({
    queryKey: ['setup-status', !!user],
    queryFn: () => api.get<SetupStatus>('/setup/status'),
    // Tablets lose Wi-Fi now and then: keep retrying in the background.
    refetchInterval: (q) => (q.state.status === 'error' ? 5_000 : false),
  })

  // Screens without the app header still need a way to move/close the desktop window.
  const bare = (screen: React.ReactNode) => (
    <>
      <DesktopTitleBar />
      {screen}
    </>
  )
  if (loading || status.isLoading) return bare(<Splash />)
  if (status.isError) return bare(<OfflineScreen retrying={status.isFetching} onRetry={() => void status.refetch()} />)
  if (status.data?.needs_setup && !user) return bare(<SetupPage />)
  if (!user) return bare(<LoginPage businessName={status.data?.business?.name} />)
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  )
}
