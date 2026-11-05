import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '@/lib/api'

import type { CartLine, PosCatalog, PosConfig, PosCustomer, QuoteLine } from './types'

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

/** Automatic promotions of the cart lines (recomputed by the backend on every change). */
export function usePosQuote(lines: CartLine[]) {
  const items = lines.map((l) => ({
    product_id: l.product_id,
    size_id: l.size?.size_id ?? null,
    qty: l.qty,
    modifier_ids: l.modifiers.map((m) => m.id),
    discount_cents: l.discount_cents,
    reward_program_id: l.reward?.program_id ?? null,
  }))
  return useQuery({
    queryKey: ['pos', 'quote', items],
    queryFn: () => api.post<{ lines: QuoteLine[] }>('/pos/quote', { items }),
    enabled: items.length > 0,
    placeholderData: keepPreviousData,
    staleTime: 30_000,
    refetchInterval: 60_000, // time-window promos (happy hour) start and end on their own
  })
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
