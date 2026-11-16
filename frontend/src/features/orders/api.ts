import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

import { api } from '@/lib/api'

import { printKitchenTicket } from './print'
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
    mutationFn: ({ id, status, reason, eta_minutes }: { id: number; status: OrderStatus; reason?: string; eta_minutes?: number }) =>
      api.post<Order>(`/orders/${id}/status`, { status, reason, eta_minutes }),
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

/**
 * «Imprimir / reimprimir comanda»: the thermal printer of its station (or the cashier's) through the backend; when
 * there is none (or it fails) the browser's print dialog gets the kitchen ticket instead.
 */
export function useReprintComanda() {
  return useMutation({
    mutationFn: async (o: Order) => {
      try {
        await api.post(`/printing/orders/${o.id}/comanda`)
        toast.success(`Comanda #${o.number} enviada a la impresora`)
      } catch (e) {
        toast.info(`${(e as Error).message} Se abre el diálogo de impresión.`, { duration: 6000 })
        printKitchenTicket(o, null)
      }
    },
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

// ---------------------------------------------------------------- online take away / delivery (Pro online_orders)

/** wa.me link with the message already written (opens WhatsApp Desktop or Web). */
export async function whatsappLink(id: number, kind: 'accepted' | 'ready' | 'dispatched' | 'generic') {
  return api.get<{ url: string; text: string }>(`/online-orders/${id}/whatsapp`, { kind })
}

export function useOnlineOrderAction() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, action }: { id: number; action: 'check-payment' | 'register-sale' | 'update-customer' }) =>
      api.post<Order>(`/online-orders/${id}/${action}`),
    onSuccess: (_o, v) => {
      if (v.action === 'update-customer') toast.success('Datos del cliente actualizados')
      if (v.action === 'register-sale') toast.success('Venta registrada')
    },
    onSettled: () => qc.invalidateQueries({ queryKey: ['orders'] }),
    onError: (e: Error) => toast.error(e.message),
  })
}
