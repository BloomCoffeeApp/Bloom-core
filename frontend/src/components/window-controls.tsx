import { Copy, Minus, Square, X } from 'lucide-react'
import { createContext, type MouseEvent, type ReactNode, useCallback, useContext, useEffect, useMemo, useState } from 'react'

import { BRAND } from '@/lib/brand'
import { cn } from '@/lib/utils'

import { Logo } from './logo'

/** Python API exposed by desktop_window.py when running inside the desktop app. */
interface DesktopApi {
  is_desktop: () => Promise<boolean>
  minimize: () => Promise<void>
  toggle_maximize: () => Promise<boolean>
  is_maximized: () => Promise<boolean>
  close: () => Promise<void>
  start_drag: () => Promise<void>
  start_resize: (edge: Edge) => Promise<void>
}

type Edge = 'top' | 'bottom' | 'left' | 'right' | 'topleft' | 'topright' | 'bottomleft' | 'bottomright'

declare global {
  interface Window {
    pywebview?: { api?: Partial<DesktopApi> }
  }
}

interface DesktopState {
  api: DesktopApi | null
  maximized: boolean
  toggleMaximize: () => void
}

const DesktopContext = createContext<DesktopState>({ api: null, maximized: false, toggleMaximize: () => {} })

const readApi = () => (window.pywebview?.api?.start_drag ? (window.pywebview.api as DesktopApi) : null)

/** Wrap the app once. Outside the desktop window (browser, tablet) everything is a no-op. */
export function DesktopProvider({ children }: { children: ReactNode }) {
  const [api, setApi] = useState<DesktopApi | null>(readApi)
  const [maximized, setMaximized] = useState(false)

  useEffect(() => {
    if (api) return
    const onReady = () => setApi(readApi())
    window.addEventListener('pywebviewready', onReady)
    return () => window.removeEventListener('pywebviewready', onReady)
  }, [api])

  useEffect(() => {
    if (!api) return
    const sync = () => void api.is_maximized().then(setMaximized)
    sync()
    // Maximize/restore from the taskbar or Win+↑ also lands here.
    window.addEventListener('resize', sync)
    return () => window.removeEventListener('resize', sync)
  }, [api])

  const toggleMaximize = useCallback(() => {
    void api?.toggle_maximize().then(setMaximized)
  }, [api])

  const value = useMemo(() => ({ api, maximized, toggleMaximize }), [api, maximized, toggleMaximize])
  return (
    <DesktopContext.Provider value={value}>
      {children}
      {api && !maximized && <ResizeEdges api={api} />}
    </DesktopContext.Provider>
  )
}

export const useDesktop = () => useContext(DesktopContext)

const INTERACTIVE = 'button, a, input, textarea, select, [role="button"], [role="menuitem"], [data-no-drag]'

/** Mouse handlers that make an element behave like a native title bar. */
export function useTitleBarDrag({ selfOnly = false }: { selfOnly?: boolean } = {}) {
  const { api, toggleMaximize } = useDesktop()
  return useMemo(() => {
    if (!api) return {}
    let lastDown = 0
    return {
      onMouseDown: (e: MouseEvent) => {
        if (e.button !== 0 || (e.target as Element).closest(INTERACTIVE)) return
        // selfOnly: drag only from the element's own background (e.g. the window margin).
        if (selfOnly && e.target !== e.currentTarget) return
        const now = performance.now()
        // Windows' drag loop swallows the second click, so detect double-click here.
        if (now - lastDown < 350) {
          lastDown = 0
          toggleMaximize()
          return
        }
        lastDown = now
        e.preventDefault()
        void api.start_drag()
      },
    }
  }, [api, toggleMaximize, selfOnly])
}

/** Minimize / maximize / close, styled like Windows 11 caption buttons. */
export function WindowControls({ className }: { className?: string }) {
  const { api, maximized, toggleMaximize } = useDesktop()
  if (!api) return null
  const btn =
    'flex h-full w-12 items-center justify-center text-muted-foreground transition-colors hover:bg-muted hover:text-foreground [&_svg]:size-4'
  return (
    <div className={cn('flex h-full shrink-0 items-stretch', className)} data-no-drag>
      <button className={btn} onClick={() => void api.minimize()} aria-label="Minimizar" title="Minimizar">
        <Minus />
      </button>
      <button
        className={btn}
        onClick={toggleMaximize}
        aria-label={maximized ? 'Restaurar' : 'Maximizar'}
        title={maximized ? 'Restaurar' : 'Maximizar'}
      >
        {maximized ? <Copy className="size-3.5! -scale-x-100" /> : <Square className="size-3.5!" />}
      </button>
      <button
        className={cn(btn, 'hover:bg-destructive hover:text-white')}
        onClick={() => void api.close()}
        aria-label="Cerrar"
        title="Cerrar"
      >
        <X />
      </button>
    </div>
  )
}

/** Standalone title bar for screens without the app header (login, setup). */
export function DesktopTitleBar() {
  const { api } = useDesktop()
  const drag = useTitleBarDrag()
  if (!api) return null
  return (
    <div className="fixed inset-x-0 top-0 z-40 flex h-10 items-center select-none" {...drag}>
      <div className="flex items-center gap-2 px-3 text-xs text-muted-foreground">
        <Logo className="size-5" />
        {BRAND.name}
      </div>
      <WindowControls className="ml-auto" />
    </div>
  )
}

const EDGES: { edge: Edge; className: string }[] = [
  { edge: 'top', className: 'top-0 inset-x-2 h-1 cursor-ns-resize' },
  { edge: 'bottom', className: 'bottom-0 inset-x-2 h-1 cursor-ns-resize' },
  { edge: 'left', className: 'left-0 inset-y-2 w-1 cursor-ew-resize' },
  { edge: 'right', className: 'right-0 inset-y-2 w-1 cursor-ew-resize' },
  { edge: 'topleft', className: 'top-0 left-0 size-2 cursor-nwse-resize' },
  { edge: 'topright', className: 'top-0 right-0 size-2 cursor-nesw-resize' },
  { edge: 'bottomleft', className: 'bottom-0 left-0 size-2 cursor-nesw-resize' },
  { edge: 'bottomright', className: 'bottom-0 right-0 size-2 cursor-nwse-resize' },
]

/** Invisible strips along the window border that start a native resize. */
function ResizeEdges({ api }: { api: DesktopApi }) {
  return (
    <>
      {EDGES.map(({ edge, className }) => (
        <div
          key={edge}
          aria-hidden
          className={cn('fixed z-[200]', className)}
          onMouseDown={(e) => {
            if (e.button !== 0) return
            e.preventDefault()
            void api.start_resize(edge)
          }}
        />
      ))}
    </>
  )
}
