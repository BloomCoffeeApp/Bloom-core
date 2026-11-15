import { createContext, type MouseEvent, type RefObject, useCallback, useContext, useEffect, useMemo, useState } from 'react'

/** Python API exposed by desktop_window.py when running inside the desktop app. */
export interface DesktopApi {
  is_desktop: () => Promise<boolean>
  minimize: () => Promise<void>
  toggle_maximize: () => Promise<boolean>
  is_maximized: () => Promise<boolean>
  is_fullscreen: () => Promise<boolean>
  toggle_fullscreen: () => Promise<boolean>
  close: () => Promise<void>
  start_drag: () => Promise<void>
  start_resize: (edge: Edge) => Promise<void>
}

export type Edge = 'top' | 'bottom' | 'left' | 'right' | 'topleft' | 'topright' | 'bottomleft' | 'bottomright'

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

export const DesktopContext = createContext<DesktopState>({ api: null, maximized: false, toggleMaximize: () => {} })

export const readApi = () => (window.pywebview?.api?.start_drag ? (window.pywebview.api as DesktopApi) : null)

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

/** Full screen that works everywhere: the native window in the desktop app (the browser API does nothing
 * inside it), the element's `requestFullscreen()` in a browser or tablet. Esc leaves it in both. */
export function useFullscreen(target?: RefObject<HTMLElement | null>) {
  const { api } = useDesktop()
  const [fullscreen, setFullscreen] = useState(false)
  const native = !!api?.toggle_fullscreen

  useEffect(() => {
    if (native) return
    const on = () => setFullscreen(document.fullscreenElement != null)
    document.addEventListener('fullscreenchange', on)
    return () => document.removeEventListener('fullscreenchange', on)
  }, [native])

  const toggle = useCallback(async () => {
    try {
      if (api?.toggle_fullscreen) setFullscreen(await api.toggle_fullscreen())
      else if (document.fullscreenElement) await document.exitFullscreen()
      else await (target?.current ?? document.documentElement).requestFullscreen()
    } catch {
      /* not allowed (iframe/webview): ignore */
    }
  }, [api, target])

  useEffect(() => {
    if (!native || !fullscreen) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') void api?.toggle_fullscreen?.().then(setFullscreen)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [api, native, fullscreen])

  return { fullscreen, toggle }
}
