import { createContext, useContext } from 'react'

export type Theme = 'light' | 'dark' | 'system'
export const THEME_KEY = 'cafe.theme'

export const ThemeContext = createContext<{ theme: Theme; setTheme: (t: Theme) => void }>({
  theme: 'system',
  setTheme: () => undefined,
})

export function readStoredTheme(): Theme {
  try {
    const v = localStorage.getItem(THEME_KEY)
    return v === 'light' || v === 'dark' ? v : 'system'
  } catch {
    return 'system'
  }
}

export const useTheme = () => useContext(ThemeContext)
