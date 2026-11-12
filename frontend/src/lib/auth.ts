import { createContext, useContext } from 'react'

import type { Permission } from '@/lib/permissions'

export type { Permission }

/** Built-in ('admin' | 'encargado' | 'cajero' | 'barista') or a custom role key. */
export type Role = string
export interface AuthUser {
  id: number
  name: string
  role: Role
  /** Display name of the role (custom roles too). */
  role_name?: string | null
  /** What this user may do (admin: everything). Only on /auth/me and login. */
  permissions?: Permission[]
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
  /** True when the user has ANY of `perms` (admin always passes). `can()` = admin only. */
  can: (...perms: Permission[]) => boolean
}

export const AuthContext = createContext<AuthState | null>(null)

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
