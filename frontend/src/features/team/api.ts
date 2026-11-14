import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

import { api, tokenStore } from '@/lib/api'

const onError = (e: Error) => toast.error(e.message)

export interface TeamInfo {
  /** `{lan_url}/equipo?k=<code>`; null when no local network was found. */
  url: string | null
  /** The code inside the link (the dialog only shows the link). */
  code: string
  lan_enabled: boolean
  lan_active: boolean
  network_public: boolean
  rotate: 'daily' | 'manual'
  lock_minutes: number
  rotated_on: string | null
}

export interface OpenSession {
  id: number
  client: string | null
  user_agent: string | null
  created_at: string
  last_seen_at: string | null
  expires_at: string
  current: boolean
}

const infoKey = ['team', 'info'] as const

export function useTeamInfo(enabled: boolean) {
  return useQuery({ queryKey: infoKey, queryFn: () => api.get<TeamInfo>('/team/info'), enabled, retry: false })
}

/** The QR is a protected PNG: fetch it with the token and expose it as an object URL. */
export function useTeamQr(enabled: boolean, version: string | null) {
  return useQuery({
    queryKey: ['team', 'qr', version],
    enabled,
    retry: false,
    staleTime: 5 * 60_000,
    queryFn: async () => {
      const token = tokenStore.get()
      const res = await fetch('/api/team/qr', { headers: token ? { Authorization: `Bearer ${token}` } : {} })
      if (!res.ok) throw new Error('No se pudo generar el código QR')
      return URL.createObjectURL(await res.blob())
    },
  })
}

export function useRotateTeamCode() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => api.post<{ ok: boolean }>('/team/rotate'),
    onSuccess: () => {
      toast.success('Código nuevo: los QR anteriores dejan de servir')
      void qc.invalidateQueries({ queryKey: ['team'] })
    },
    onError,
  })
}

export function useSaveTeamConfig() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { rotate?: 'daily' | 'manual'; lock_minutes?: number }) => api.put('/team/config', data),
    onSuccess: () => {
      toast.success('Cambios guardados')
      void qc.invalidateQueries({ queryKey: ['team'] })
    },
    onError,
  })
}

const sessionsKey = (userId: number) => ['team', 'sessions', userId] as const

export function useUserSessions(userId: number, enabled = true) {
  return useQuery({
    queryKey: sessionsKey(userId),
    queryFn: () => api.get<OpenSession[]>(`/users/${userId}/sessions`),
    enabled,
    refetchInterval: 15_000,
  })
}

export function useDisconnectSession(userId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (sessionId: number) => api.delete(`/users/${userId}/sessions/${sessionId}`),
    onSuccess: () => {
      toast.success('Sesión desconectada')
      void qc.invalidateQueries({ queryKey: sessionsKey(userId) })
    },
    onError,
  })
}

/** Short, human description of a browser from its user agent (no library: only what a café owner can recognize). */
export function deviceLabel(ua: string | null): string {
  if (!ua) return 'Dispositivo desconocido'
  const os = /iPhone|iPad/.test(ua)
    ? 'iPhone / iPad'
    : /Android/.test(ua)
      ? 'Android'
      : /Windows/.test(ua)
        ? 'Windows'
        : /Mac OS/.test(ua)
          ? 'Mac'
          : /Linux/.test(ua)
            ? 'Linux'
            : 'Dispositivo'
  const browser = /Edg\//.test(ua) ? 'Edge' : /Firefox\//.test(ua) ? 'Firefox' : /Chrome\//.test(ua) ? 'Chrome' : /Safari\//.test(ua) ? 'Safari' : ''
  return browser ? `${os} · ${browser}` : os
}
