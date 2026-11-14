import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'

import { api, ApiError, setUnauthorizedHandler, tokenStore } from '@/lib/api'
import { AuthContext, type AuthUser, type LoginResponse, type Permission } from '@/lib/auth'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  // Without a stored token there is no session to restore, so we start out not loading.
  const [loading, setLoading] = useState(() => !!tokenStore.get())
  const qc = useQueryClient()

  // Idempotent: logging out and a late 401 (a request sent just before the session ended) both end up here. A second
  // `qc.clear()` after the login screen mounted would drop its in-flight users query and leave the list empty for good.
  const signedIn = useRef(false) // also true when the browser refuses to store the token
  const clear = useCallback(() => {
    if (!signedIn.current && !tokenStore.get()) return
    signedIn.current = false
    tokenStore.set(null)
    setUser(null)
    qc.clear()
  }, [qc])

  useEffect(() => {
    setUnauthorizedHandler(clear)
    if (!tokenStore.get()) return
    api
      .get<AuthUser>('/auth/me')
      .then((u) => {
        signedIn.current = true
        setUser(u)
      })
      .catch((e) => {
        // Only a 401 means the session is gone. A network error, a request cut by navigating away or reloading, or a
        // 5xx must NOT log the person out: the token stays and the next load tries again.
        if (e instanceof ApiError && e.status === 401) tokenStore.set(null)
      })
      .finally(() => setLoading(false))
  }, [clear])

  const completeLogin = useCallback((res: LoginResponse) => {
    tokenStore.set(res.token)
    signedIn.current = true
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
    (...perms: Permission[]) =>
      !!user && (user.role === 'admin' || perms.some((p) => user.permissions?.includes(p))),
    [user],
  )

  const value = useMemo(
    () => ({ user, loading, login, completeLogin, logout, can }),
    [user, loading, login, completeLogin, logout, can],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
