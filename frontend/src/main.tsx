import './index.css'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import App from '@/App'
import { DemoBanner } from '@/components/demo-banner'
import { Toaster } from '@/components/ui/sonner'
import { DesktopProvider } from '@/components/window-controls'
import { TooltipProvider } from '@/components/ui/tooltip'
import { AuthProvider } from '@/lib/auth-provider'
import { registerPwa } from '@/lib/pwa'
import { ThemeProvider } from '@/lib/theme-provider'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 15_000, refetchOnWindowFocus: false, retry: 1 },
  },
})

registerPwa()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <TooltipProvider delayDuration={300}>
            <DesktopProvider>
              <App />
              <DemoBanner />
              <Toaster richColors position="top-right" />
            </DesktopProvider>
          </TooltipProvider>
        </AuthProvider>
      </QueryClientProvider>
    </ThemeProvider>
  </StrictMode>,
)
