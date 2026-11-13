import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '@/lib/api'
import { idempotencyKeyFor, releaseIdempotencyKey } from '@/lib/idempotency'

import type { PaymentMethod, SaleDetail, SaleIn, SaleList, SalesFilters, TicketData } from './types'

export const salesKeys = {
  all: ['sales'] as const,
  list: (f: SalesFilters) => ['sales', 'list', f] as const,
  detail: (id: number) => ['sales', 'detail', id] as const,
  methods: ['sales', 'payment-methods'] as const,
}

export function usePaymentMethods() {
  return useQuery({
    queryKey: salesKeys.methods,
    queryFn: () => api.get<PaymentMethod[]>('/payment-methods'),
    staleTime: 5 * 60_000,
  })
}

export function useSales(filters: SalesFilters) {
  return useQuery({
    queryKey: salesKeys.list(filters),
    queryFn: () => api.get<SaleList>('/sales', { ...filters }),
    placeholderData: keepPreviousData,
  })
}

export function useSale(id: number | null) {
  return useQuery({
    queryKey: salesKeys.detail(id ?? 0),
    queryFn: () => api.get<SaleDetail>(`/sales/${id}`),
    enabled: id != null,
  })
}

export function useCreateSale() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: SaleIn) => api.post<SaleDetail>('/sales', body, { idempotencyKey: idempotencyKeyFor('sale', body) }),
    onSuccess: () => {
      releaseIdempotencyKey('sale')
      qc.invalidateQueries({ queryKey: salesKeys.all })
      qc.invalidateQueries({ queryKey: ['cash'] })
      qc.invalidateQueries({ queryKey: ['pos', 'customers'] })
      qc.invalidateQueries({ queryKey: ['orders'] }) // open tabs + the order screen
    },
  })
}

export function useVoidSale() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, reason }: { id: number; reason: string }) =>
      api.post<SaleDetail>(`/sales/${id}/void`, { reason }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: salesKeys.all })
      qc.invalidateQueries({ queryKey: ['cash'] })
    },
  })
}

export const fetchTicket = (id: number) => api.get<TicketData>(`/sales/${id}/ticket`)
