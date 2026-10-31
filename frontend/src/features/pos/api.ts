import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '@/lib/api'

import type { PosCatalog, PosConfig, PosCustomer } from './types'

export const posKeys = {
  catalog: ['pos', 'catalog'] as const,
  config: ['pos', 'config'] as const,
  customers: (q: string) => ['pos', 'customers', q] as const,
}

export function usePosCatalog() {
  return useQuery({ queryKey: posKeys.catalog, queryFn: () => api.get<PosCatalog>('/pos/catalog'), staleTime: 60_000 })
}

export function usePosConfig() {
  return useQuery({ queryKey: posKeys.config, queryFn: () => api.get<PosConfig>('/pos/config'), staleTime: 5 * 60_000 })
}

export function useCustomerSearch(q: string, enabled: boolean) {
  return useQuery({
    queryKey: posKeys.customers(q),
    queryFn: () => api.get<PosCustomer[]>('/customers', { q, limit: 30 }),
    enabled,
    placeholderData: keepPreviousData,
  })
}

export function useCreateCustomer() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { name: string; phone?: string | null }) => api.post<PosCustomer>('/customers', body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['pos', 'customers'] })
      qc.invalidateQueries({ queryKey: ['customers'] })
    },
  })
}
