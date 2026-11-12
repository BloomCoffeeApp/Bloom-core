import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

import { api } from '@/lib/api'

import { salesKeys } from '../sales/api'
import type { Charge, CollectStatus, CustomerScreen, PosChargeIn, SaleChargeInfo, ScreenState, TransferInfo } from './types'

export const collectKeys = {
  status: ['collect', 'status'] as const,
  screens: ['collect', 'screens'] as const,
  charge: (id: number) => ['collect', 'charge', id] as const,
  sale: (id: number) => ['collect', 'sale', id] as const,
}

export function useCollectStatus(enabled = true) {
  return useQuery({
    queryKey: collectKeys.status,
    queryFn: () => api.get<CollectStatus>('/collect/status'),
    enabled,
    staleTime: 30_000,
  })
}

function useInvalidateCollect() {
  const qc = useQueryClient()
  return () => {
    qc.invalidateQueries({ queryKey: ['collect'] })
    qc.invalidateQueries({ queryKey: salesKeys.methods })
    qc.invalidateQueries({ queryKey: ['settings', 'payment-methods'] })
    qc.invalidateQueries({ queryKey: ['settings'] })
  }
}

export interface CollectConfigIn {
  provider?: string | null
  transfer?: TransferInfo
  expires_minutes?: number
  point_device_id?: string | null
  point_device_name?: string | null
  default_screen_id?: number | null
}

export function useSaveCollectConfig() {
  const invalidate = useInvalidateCollect()
  return useMutation({
    mutationFn: (body: CollectConfigIn) => api.put<CollectStatus>('/collect/config', body),
    onSuccess: () => {
      invalidate()
      toast.success('Cobros actualizados')
    },
    onError: (e) => toast.error(e.message),
  })
}

export function useCreatePosCharge() {
  return useMutation({ mutationFn: (body: PosChargeIn) => api.post<Charge>('/collect/pos-charges', body) })
}

/** Polls an open charge every 1.5 s (the backend asks the provider when a poll is due). */
export function useCharge(id: number | null) {
  return useQuery({
    queryKey: collectKeys.charge(id ?? 0),
    queryFn: () => api.get<Charge>(`/collect/charges/${id}`),
    enabled: id != null,
    refetchInterval: (q) => (q.state.data && q.state.data.status !== 'pending' ? false : 1500),
    refetchIntervalInBackground: true,
  })
}

export function useChargeAction() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, action, body }: { id: number; action: 'cancel' | 'confirm' | 'retry' | 'simulate'; body?: unknown }) =>
      api.post<Charge>(`/collect/charges/${id}/${action}`, body),
    onSuccess: (ch) => qc.setQueryData(collectKeys.charge(ch.id), ch),
    onError: (e) => toast.error(e.message),
  })
}

export function useScreens(enabled = true) {
  return useQuery({ queryKey: collectKeys.screens, queryFn: () => api.get<CustomerScreen[]>('/collect/screens'), enabled })
}

export function useScreenMutations() {
  const invalidate = useInvalidateCollect()
  const opts = { onSuccess: invalidate, onError: (e: Error) => toast.error(e.message) }
  return {
    create: useMutation({ mutationFn: (name: string) => api.post<CustomerScreen>('/collect/screens', { name }), ...opts }),
    update: useMutation({
      mutationFn: ({ id, ...body }: { id: number; name?: string; active?: boolean; rotate?: boolean }) =>
        api.patch<CustomerScreen>(`/collect/screens/${id}`, body),
      ...opts,
    }),
    remove: useMutation({ mutationFn: (id: number) => api.delete(`/collect/screens/${id}`), ...opts }),
  }
}

export function useSaleCharge(saleId: number | null, enabled = true) {
  return useQuery({
    queryKey: collectKeys.sale(saleId ?? 0),
    queryFn: () => api.get<SaleChargeInfo>(`/collect/sales/${saleId}`),
    enabled: enabled && saleId != null,
  })
}

export function useRefundSale(saleId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { amount_cents: number | null; reason: string | null; void_sale: boolean }) =>
      api.post<SaleChargeInfo>(`/collect/sales/${saleId}/refund`, body),
    onSuccess: (info) => {
      qc.setQueryData(collectKeys.sale(saleId), info)
      qc.invalidateQueries({ queryKey: salesKeys.all })
      qc.invalidateQueries({ queryKey: ['cash'] })
      toast.success('Devolución hecha en Mercado Pago')
    },
    onError: (e) => toast.error(e.message),
  })
}

/** Public: what a customer screen shows now (no login, the screen's token). */
export function useScreenState(token: string) {
  return useQuery({
    queryKey: ['public', 'customer-screen', token],
    queryFn: () => api.get<ScreenState>('/public/customer-screen', { token }),
    refetchInterval: 1500,
    refetchIntervalInBackground: true,
    retry: 1,
  })
}
