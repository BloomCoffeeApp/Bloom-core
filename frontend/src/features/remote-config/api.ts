import { useQuery } from '@tanstack/react-query'

import { api } from '@/lib/api'

/** Mirrors backend app/routers/remote_config.py */
export interface Announcement {
  id: number
  title: string
  body: string
  level: 'info' | 'warning' | 'critical'
}

export interface SupportInfo {
  email: string | null
  whatsapp: string | null
  terms_url: string | null
  privacy_url: string | null
}

export interface RemoteConfig {
  announcements: Announcement[]
  support: SupportInfo
  min_version: string | null
  required: boolean
  release_notes_url: string | null
}

/** What the vendor's signed remote config says for this installation (cached by the backend; works offline). */
export function useRemoteConfig() {
  return useQuery({
    queryKey: ['remote-config'],
    queryFn: () => api.get<RemoteConfig>('/remote-config'),
    staleTime: 10 * 60_000,
    refetchInterval: 30 * 60_000,
    retry: false,
  })
}
