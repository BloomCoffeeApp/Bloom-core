import { useQuery } from '@tanstack/react-query'
import { Coffee } from 'lucide-react'
import { Suspense } from 'react'
import { BrowserRouter } from 'react-router'

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

function Splash() {
  return (
    <div className="flex min-h-svh items-center justify-center">
      <Coffee className="size-10 animate-pulse text-primary" />
    </div>
  )
}

export default function App() {
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

function PrivateApp() {
  const { user, loading } = useAuth()
  const status = useQuery({
    queryKey: ['setup-status', !!user],
    queryFn: () => api.get<SetupStatus>('/setup/status'),
  })

  // Screens without the app header still need a way to move/close the desktop window.
  const bare = (screen: React.ReactNode) => (
    <>
      <DesktopTitleBar />
      {screen}
    </>
  )
  if (loading || status.isLoading) return bare(<Splash />)
  if (status.isError)
    return bare(
      <div className="flex min-h-svh items-center justify-center p-6 text-center text-muted-foreground">
        No se pudo conectar con el servidor de la app. Reiniciá la aplicación.
      </div>,
    )
  if (status.data?.needs_setup && !user) return bare(<SetupPage />)
  if (!user) return bare(<LoginPage businessName={status.data?.business?.name} />)
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  )
}
