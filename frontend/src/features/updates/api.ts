import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

import { api } from '@/lib/api'

import type { UpdateState, UpdateStatus } from './types'

export const updateKeys = { status: ['updates', 'status'] as const }

const WORKING: UpdateState[] = ['checking', 'downloading', 'verifying', 'installing']

/** Admin only. Polls fast while an update is being downloaded/installed, slowly otherwise. */
export function useUpdateStatus(enabled: boolean) {
  return useQuery({
    queryKey: updateKeys.status,
    queryFn: () => api.get<UpdateStatus>('/updates'),
    enabled,
    retry: false,
    refetchInterval: (q) => (q.state.data && WORKING.includes(q.state.data.state) ? 1000 : 30 * 60_000),
  })
}

export function useCheckUpdates() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => api.post<UpdateStatus>('/updates/check'),
    onSuccess: (s) => qc.setQueryData(updateKeys.status, s),
    onError: (e: Error) => toast.error(e.message),
  })
}

export function useInstallUpdate() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => api.post<UpdateStatus>('/updates/install'),
    onSuccess: (s) => qc.setQueryData(updateKeys.status, s),
    onError: (e: Error) => toast.error(e.message),
  })
}
