import { useQueryClient } from '@tanstack/react-query'
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

import { api, setUnauthorizedHandler, tokenStore } from '@/lib/api'

export type Role = 'admin' | 'encargado' | 'cajero' | 'barista'
export interface AuthUser {
  id: number
  name: string
  role: Role
  color: string
}
interface LoginResponse {
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

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [loading, setLoading] = useState(true)
  const qc = useQueryClient()

  const clear = useCallback(() => {
    tokenStore.set(null)
    setUser(null)
    qc.clear()
  }, [qc])

  useEffect(() => {
    setUnauthorizedHandler(clear)
    if (!tokenStore.get()) {
      setLoading(false)
      return
    }
    api
      .get<AuthUser>('/auth/me')
      .then(setUser)
      .catch(() => tokenStore.set(null))
      .finally(() => setLoading(false))
  }, [clear])

  const completeLogin = useCallback((res: LoginResponse) => {
    tokenStore.set(res.token)
    setUser(res.user)
  }, [])

  const login = useCallback(
    async (userId: number, pin: string) => {
      completeLogin(await api.post<LoginResponse>('/auth/login', { user_id: userId, pin }))
    },
    [completeLogin],
  )

  const logout = useCallback(async () => {
    await api.post('/auth/logout').catch(() => undefined)
    clear()
  }, [clear])

  const can = useCallback(
    (...roles: Role[]) => !!user && (user.role === 'admin' || roles.includes(user.role)),
    [user],
  )

  const value = useMemo(
    () => ({ user, loading, login, completeLogin, logout, can }),
    [user, loading, login, completeLogin, logout, can],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
