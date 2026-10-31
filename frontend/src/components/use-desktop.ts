import { createContext, type MouseEvent, useContext, useMemo } from 'react'

/** Python API exposed by desktop_window.py when running inside the desktop app. */
export interface DesktopApi {
  is_desktop: () => Promise<boolean>
  minimize: () => Promise<void>
  toggle_maximize: () => Promise<boolean>
  is_maximized: () => Promise<boolean>
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
