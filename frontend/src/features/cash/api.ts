import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '@/lib/api'

import type { CashMovement, CashSession, CashSessionDetail, CashSessionListItem } from './types'

export const cashKeys = {
  all: ['cash'] as const,
  current: ['cash', 'current'] as const,
  sessions: ['cash', 'sessions'] as const,
  session: (id: number) => ['cash', 'session', id] as const,
}

export function useCurrentCash() {
  return useQuery({
    queryKey: cashKeys.current,
    queryFn: () => api.get<CashSession | null>('/cash/current'),
    refetchInterval: 60_000,
  })
}

export function useCashSessions() {
  return useQuery({ queryKey: cashKeys.sessions, queryFn: () => api.get<CashSessionListItem[]>('/cash/sessions') })
}

export function useCashSession(id: number | null) {
  return useQuery({
    queryKey: cashKeys.session(id ?? 0),
    queryFn: () => api.get<CashSessionDetail>(`/cash/sessions/${id}`),
    enabled: id != null,
  })
}

export function useOpenCash() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (opening_cents: number) => api.post<CashSession>('/cash/open', { opening_cents }),
    onSuccess: () => qc.invalidateQueries({ queryKey: cashKeys.all }),
  })
}

export function useCashMovement() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { type: 'in' | 'out'; amount_cents: number; reason: string }) =>
      api.post<CashMovement>('/cash/movements', body),
    onSuccess: () => qc.invalidateQueries({ queryKey: cashKeys.all }),
  })
}

export function useCloseCash() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { counts: { payment_method: string; counted_cents: number }[]; notes?: string }) =>
      api.post<CashSessionDetail>('/cash/close', body),
    // Not awaited on purpose: once `current` refetches as null the close dialog unmounts, and the
    // caller's mutate() onSuccess (which opens the Z report) would never run.
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: cashKeys.all })
    },
  })
}
