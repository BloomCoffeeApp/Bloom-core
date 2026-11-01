import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

import { api } from '@/lib/api'

import type { Board, Order, OrderStatus, OrdersSettings, Tab } from './types'

export const ordersKeys = {
  board: (station: number | null) => ['orders', 'board', station] as const,
  settings: ['orders', 'settings'] as const,
  tabs: ['orders', 'tabs'] as const,
}

/** Board polling interval. Polling (not SSE) on purpose: see PLAN.md §9. */
export const BOARD_POLL_MS = 2_000

export function useBoard(station: number | null) {
  return useQuery({
    queryKey: ordersKeys.board(station),
    queryFn: () => api.get<Board>('/orders/board', station ? { station_id: station } : undefined),
    refetchInterval: BOARD_POLL_MS,
    refetchIntervalInBackground: true, // a bar tablet keeps ringing with the screen in the background
    staleTime: 0,
  })
}

export function useSetOrderStatus() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, status, reason }: { id: number; status: OrderStatus; reason?: string }) =>
      api.post<Order>(`/orders/${id}/status`, { status, reason }),
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ['orders'] })
    },
    onError: (e: Error) => toast.error(e.message),
  })
}

export function useResolveCall() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => api.post(`/waiter-calls/${id}/resolve`),
    onSettled: () => qc.invalidateQueries({ queryKey: ['orders', 'board'] }),
    onError: (e: Error) => toast.error(e.message),
  })
}

export function useOrdersSettings() {
  return useQuery({ queryKey: ordersKeys.settings, queryFn: () => api.get<OrdersSettings>('/orders/settings') })
}

export function useSaveOrdersSettings() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (s: OrdersSettings) => api.put<OrdersSettings>('/orders/settings', s),
    onSuccess: (s) => {
      qc.setQueryData(ordersKeys.settings, s)
      qc.invalidateQueries({ queryKey: ['orders'] })
      toast.success('Pantalla de pedidos guardada')
    },
    onError: (e: Error) => toast.error(e.message),
  })
}

/** Open tables waiting to be charged (POS). */
export function useOpenTabs(enabled = true) {
  return useQuery({
    queryKey: ordersKeys.tabs,
    queryFn: () => api.get<Tab[]>('/tabs'),
    enabled,
    refetchInterval: 10_000,
  })
}
