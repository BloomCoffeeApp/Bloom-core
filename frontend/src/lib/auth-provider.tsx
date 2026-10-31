import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'

import { api, setUnauthorizedHandler, tokenStore } from '@/lib/api'
import { AuthContext, type AuthUser, type LoginResponse, type Role } from '@/lib/auth'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  // Without a stored token there is no session to restore, so we start out not loading.
  const [loading, setLoading] = useState(() => !!tokenStore.get())
  const qc = useQueryClient()

  const clear = useCallback(() => {
    tokenStore.set(null)
    setUser(null)
    qc.clear()
  }, [qc])

  useEffect(() => {
    setUnauthorizedHandler(clear)
    if (!tokenStore.get()) return
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
