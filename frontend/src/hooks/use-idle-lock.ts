import { useQuery } from '@tanstack/react-query'
import { useEffect } from 'react'

import { api } from '@/lib/api'
import { useAuth } from '@/lib/auth'

/** Logs the user out (back to the PIN screen) after N idle minutes (setting "lock_minutes"; 0 = off). */
export function useIdleLock() {
  const { logout, user } = useAuth()
  const { data } = useQuery({
    queryKey: ['settings'],
    queryFn: () => api.get<Record<string, unknown>>('/settings'),
    enabled: !!user,
    staleTime: 60_000,
  })
  const minutes = Number(data?.lock_minutes ?? 10)

  useEffect(() => {
    if (!user || !minutes) return
    let timer: number
    const reset = () => {
      window.clearTimeout(timer)
      timer = window.setTimeout(() => logout(), minutes * 60_000)
    }
    const events = ['pointerdown', 'keydown', 'touchstart', 'wheel'] as const
    events.forEach((e) => window.addEventListener(e, reset, { passive: true }))
    reset()
    return () => {
      window.clearTimeout(timer)
      events.forEach((e) => window.removeEventListener(e, reset))
    }
  }, [user, minutes, logout])
}
