import { createContext, useContext } from 'react'

export type Role = 'admin' | 'encargado' | 'cajero' | 'barista'
export interface AuthUser {
  id: number
  name: string
  role: Role
  color: string
  /** Free plan: can't log in (only in the login list). */
  locked?: boolean
}
export interface LoginResponse {
  token: string
  user: AuthUser
}

interface AuthState {
  user: AuthUser | null
  loading: boolean
  login: (userId: number, pin: string) => Promise<void>
  completeLogin: (res: LoginResponse) => void
  logout: () => Promise<void>
  /** True when the user's role is allowed (admin always passes). */
  can: (...roles: Role[]) => boolean
}

export const AuthContext = createContext<AuthState | null>(null)

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
