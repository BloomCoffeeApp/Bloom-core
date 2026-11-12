/**
 * Installable app (PWA) support for phones and tablets that use Bloom over the shop's Wi-Fi.
 *
 * Service workers only run in a *secure context*: localhost or https. A tablet that opens
 * http://192.168.x.x:port is NOT one, so there the app is installable only as a home-screen
 * shortcut (manifest, no offline shell). See Configuración → Red local for the options.
 * The desktop window (pywebview) never registers a worker: it always loads the local server.
 */
import { toast } from 'sonner'

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

let installEvent: BeforeInstallPromptEvent | null = null
const listeners = new Set<() => void>()
const notify = () => listeners.forEach((fn) => fn())

export const pwaSupport = () => ({
  secure: window.isSecureContext,
  serviceWorker: 'serviceWorker' in navigator && window.isSecureContext,
  installed: window.matchMedia?.('(display-mode: standalone)').matches || ('standalone' in navigator && !!(navigator as { standalone?: boolean }).standalone),
  canPrompt: !!installEvent,
})

export function onPwaChange(fn: () => void) {
  listeners.add(fn)
  return () => void listeners.delete(fn)
}

/** Shows the browser's install dialog when it offered one (Chrome/Edge on https or localhost). */
export async function promptInstall(): Promise<boolean> {
  if (!installEvent) return false
  await installEvent.prompt()
  const { outcome } = await installEvent.userChoice
  installEvent = null
  notify()
  return outcome === 'accepted'
}

const isDesktopWindow = () => !!(window as { pywebview?: unknown }).pywebview

function offerUpdate(reg: ServiceWorkerRegistration) {
  const waiting = reg.waiting
  if (!waiting || !navigator.serviceWorker.controller) return
  toast('Hay una versión nueva de la app', {
    id: 'pwa-update',
    duration: Infinity,
    description: 'Actualizá para usar la última versión instalada en la PC del local.',
    action: { label: 'Actualizar', onClick: () => waiting.postMessage({ type: 'SKIP_WAITING' }) },
  })
}

export function registerPwa() {
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault()
    installEvent = e as BeforeInstallPromptEvent
    notify()
  })
  window.addEventListener('appinstalled', () => {
    installEvent = null
    notify()
  })
  if (!import.meta.env.PROD || !('serviceWorker' in navigator) || !window.isSecureContext) return
  window.addEventListener('load', () => {
    // pywebview injects its API right after load: give it a moment before deciding.
    window.setTimeout(() => {
      if (isDesktopWindow()) {
        void navigator.serviceWorker.getRegistrations().then((regs) => regs.forEach((r) => void r.unregister()))
        return
      }
      let reloading = false
      navigator.serviceWorker.addEventListener('controllerchange', () => {
        if (reloading) return
        reloading = true
        window.location.reload()
      })
      navigator.serviceWorker
        .register('/sw.js', { scope: '/' })
        .then((reg) => {
          offerUpdate(reg)
          reg.addEventListener('updatefound', () => {
            reg.installing?.addEventListener('statechange', () => offerUpdate(reg))
          })
          // Tablets stay open all day: look for a new version every 30 minutes.
          window.setInterval(() => void reg.update().catch(() => undefined), 30 * 60_000)
        })
        .catch(() => undefined)
    }, 1500)
  })
}
