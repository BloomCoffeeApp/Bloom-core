import { useQuery } from '@tanstack/react-query'

import { api } from '@/lib/api'

import type { BaristaToday, CashCurrent, Dashboard, OpenAlert } from './types'

export function useDashboard(from: string, to: string) {
  return useQuery({
    queryKey: ['dashboard', from, to],
    queryFn: () => api.get<Dashboard>('/dashboard', { from, to }),
    placeholderData: (prev) => prev,
    refetchInterval: 60_000,
  })
}

/** Endpoints owned by other modules: never retry, the block just shows empty if they fail. */
export function useOpenAlerts() {
  return useQuery({
    queryKey: ['dashboard', 'alerts-open'],
    queryFn: () => api.get<OpenAlert[]>('/alerts', { status: 'open' }),
    retry: false,
    refetchInterval: 60_000,
  })
}

export function useBaristaToday(enabled: boolean) {
  return useQuery({
    queryKey: ['dashboard', 'barista-today'],
    queryFn: () => api.get<BaristaToday>('/barista/today'),
    retry: false,
    enabled,
  })
}

export function useCashCurrent(enabled: boolean) {
  return useQuery({
    queryKey: ['dashboard', 'cash-current'],
    queryFn: () => api.get<CashCurrent | null>('/cash/current'),
    retry: false,
    enabled,
    refetchInterval: 60_000,
  })
}
