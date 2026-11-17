import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

import { api } from '@/lib/api'
import { idempotencyKeyFor, releaseIdempotencyKey } from '@/lib/idempotency'

import type {
  AccountMovement,
  Customer,
  CustomerDetail,
  CustomerInput,
  CustomerListItem,
  CustomerSalesPage,
  CustomerStats,
  LoyaltyTx,
  Segment,
} from './types'

export const customerKeys = {
  all: ['customers'] as const,
  list: (segment: Segment, q: string) => ['customers', 'list', segment, q] as const,
  stats: ['customers', 'stats'] as const,
  detail: (id: number) => ['customers', 'detail', id] as const,
  sales: (id: number, page: number) => ['customers', 'sales', id, page] as const,
}

const onError = (e: Error) => toast.error(e.message)

export function useCustomers(segment: Segment, q: string) {
  return useQuery({
    queryKey: customerKeys.list(segment, q),
    queryFn: () =>
      api.get<CustomerListItem[]>('/customers', {
        segment: segment === 'todos' ? undefined : segment,
        q: q || undefined,
        limit: q ? 200 : undefined,
        order: segment === 'deudores' ? 'balance' : segment === 'frecuentes' ? 'last_visit' : 'name',
      }),
    placeholderData: keepPreviousData,
  })
}

export function useCustomerStats() {
  return useQuery({ queryKey: customerKeys.stats, queryFn: () => api.get<CustomerStats>('/customers/stats') })
}

export function useCustomer(id: number) {
  return useQuery({
    queryKey: customerKeys.detail(id),
    queryFn: () => api.get<CustomerDetail>(`/customers/${id}`),
    enabled: Number.isFinite(id),
  })
}

export function useCustomerSales(id: number, page: number) {
  return useQuery({
    queryKey: customerKeys.sales(id, page),
    queryFn: () => api.get<CustomerSalesPage>(`/customers/${id}/sales`, { page, page_size: 10 }),
    placeholderData: keepPreviousData,
  })
}

export function useSaveCustomer() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id?: number; data: Partial<CustomerInput> & { active?: boolean } }) =>
      id ? api.patch<Customer>(`/customers/${id}`, data) : api.post<Customer>('/customers', data),
    onSuccess: (_c, vars) => {
      qc.invalidateQueries({ queryKey: customerKeys.all })
      toast.success(vars.id ? 'Cliente actualizado' : 'Cliente creado')
    },
    onError,
  })
}

export function useDeactivateCustomer() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => api.delete(`/customers/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: customerKeys.all })
      toast.success('Cliente desactivado')
    },
    onError,
  })
}

export function useRegisterPayment(id: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { amount_cents: number; method: string }) =>
      api.post<AccountMovement>(`/customers/${id}/payments`, body, { idempotencyKey: idempotencyKeyFor(`payment-${id}`, body) }),
    onSuccess: () => {
      releaseIdempotencyKey(`payment-${id}`)
      qc.invalidateQueries({ queryKey: customerKeys.all })
      qc.invalidateQueries({ queryKey: ['alerts'] })
      toast.success('Pago registrado')
    },
    onError,
  })
}

export function useAdjustPoints(id: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { points: number; reason: string }) => api.post<LoyaltyTx>(`/customers/${id}/points`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: customerKeys.all })
      toast.success('Puntos ajustados')
    },
    onError,
  })
}

export function useExportCustomerData() {
  return useMutation({
    mutationFn: (id: number) => api.download(`/customers/${id}/export`, undefined, `cliente-${id}-datos.json`),
    onSuccess: () => toast.success('Descargamos los datos del cliente'),
    onError,
  })
}

export function useAnonymizeCustomer() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, reason }: { id: number; reason?: string }) =>
      api.post(`/customers/${id}/anonymize`, { confirm: true, reason: reason || null }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: customerKeys.all })
      toast.success('Datos personales borrados. Las ventas se conservan.')
    },
    onError,
  })
}
