import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

import { api } from '@/lib/api'

import type {
  InventoryCount,
  Movement,
  StockCategory,
  StockItem,
  StockItemInput,
  StockSummary,
  SuggestionGroup,
} from './types'

export const stockKeys = {
  all: ['stock'] as const,
  items: (includeInactive = false) => ['stock', 'items', includeInactive] as const,
  categories: ['stock', 'categories'] as const,
  summary: ['stock', 'summary'] as const,
  movements: (id: number) => ['stock', 'movements', id] as const,
  counts: ['stock', 'counts'] as const,
  count: (id: number) => ['stock', 'count', id] as const,
  suggestions: ['stock', 'suggestions'] as const,
}

const onError = (e: Error) => toast.error(e.message)

export function useStockItems(opts: { includeInactive?: boolean; enabled?: boolean } = {}) {
  return useQuery({
    queryKey: stockKeys.items(!!opts.includeInactive),
    queryFn: () => api.get<StockItem[]>('/stock/items', { include_inactive: opts.includeInactive || undefined }),
    enabled: opts.enabled ?? true,
  })
}

export function useStockCategories() {
  return useQuery({ queryKey: stockKeys.categories, queryFn: () => api.get<StockCategory[]>('/stock/categories') })
}

export function useStockSummary() {
  return useQuery({ queryKey: stockKeys.summary, queryFn: () => api.get<StockSummary>('/stock/summary') })
}

export function useMovements(id: number | null) {
  return useQuery({
    queryKey: stockKeys.movements(id ?? 0),
    queryFn: () => api.get<Movement[]>(`/stock/items/${id}/movements`),
    enabled: id != null,
  })
}

export function useSuggestions() {
  return useQuery({ queryKey: stockKeys.suggestions, queryFn: () => api.get<SuggestionGroup[]>('/stock/suggestions') })
}

export function useCounts() {
  return useQuery({ queryKey: stockKeys.counts, queryFn: () => api.get<InventoryCount[]>('/stock/counts') })
}

export function useCount(id: number | null) {
  return useQuery({
    queryKey: stockKeys.count(id ?? 0),
    queryFn: () => api.get<InventoryCount>(`/stock/counts/${id}`),
    enabled: id != null,
  })
}

function useInvalidateStock() {
  const qc = useQueryClient()
  return () => qc.invalidateQueries({ queryKey: stockKeys.all })
}

export function useSaveStockItem() {
  const invalidate = useInvalidateStock()
  return useMutation({
    mutationFn: ({ id, data }: { id?: number; data: Partial<StockItemInput> }) =>
      id ? api.patch<StockItem>(`/stock/items/${id}`, data) : api.post<StockItem>('/stock/items', data),
    onSuccess: (_d, v) => {
      invalidate()
      toast.success(v.id ? 'Insumo actualizado' : 'Insumo creado')
    },
    onError,
  })
}

export function useDeactivateStockItem() {
  const invalidate = useInvalidateStock()
  return useMutation({
    mutationFn: (id: number) => api.delete(`/stock/items/${id}`),
    onSuccess: () => {
      invalidate()
      toast.success('Insumo desactivado')
    },
    onError,
  })
}

export function useAdjustStock() {
  const invalidate = useInvalidateStock()
  return useMutation({
    mutationFn: (body: { stock_item_id: number; new_qty?: number; delta?: number; reason: string }) =>
      api.post<StockItem>('/stock/adjust', body),
    onSuccess: () => {
      invalidate()
      toast.success('Stock ajustado')
    },
    onError,
  })
}

export function useRegisterWaste() {
  const invalidate = useInvalidateStock()
  return useMutation({
    mutationFn: (body: { stock_item_id: number; qty: number; reason: string }) => api.post<StockItem>('/stock/waste', body),
    onSuccess: () => {
      invalidate()
      toast.success('Merma registrada')
    },
    onError,
  })
}

export function useSaveStockCategory() {
  const invalidate = useInvalidateStock()
  return useMutation({
    mutationFn: ({ id, name }: { id?: number; name: string }) =>
      id ? api.patch<StockCategory>(`/stock/categories/${id}`, { name }) : api.post<StockCategory>('/stock/categories', { name }),
    onSuccess: () => {
      invalidate()
      toast.success('Categoría guardada')
    },
    onError,
  })
}

export function useDeleteStockCategory() {
  const invalidate = useInvalidateStock()
  return useMutation({
    mutationFn: (id: number) => api.delete(`/stock/categories/${id}`),
    onSuccess: () => {
      invalidate()
      toast.success('Categoría eliminada')
    },
    onError,
  })
}

export function useCreateCount() {
  const invalidate = useInvalidateStock()
  return useMutation({
    mutationFn: (body: { category_id: number | null; notes?: string }) => api.post<InventoryCount>('/stock/counts', body),
    onSuccess: () => invalidate(),
    onError,
  })
}

export function useSetCounted(countId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (items: { id: number; counted_qty: number | null }[]) =>
      api.patch<InventoryCount>(`/stock/counts/${countId}/items`, { items }),
    onSuccess: (data) => qc.setQueryData(stockKeys.count(countId), data),
    onError,
  })
}

export function useCountAction(countId: number) {
  const invalidate = useInvalidateStock()
  return useMutation({
    mutationFn: (action: 'apply' | 'cancel') => api.post<InventoryCount>(`/stock/counts/${countId}/${action}`),
    onSuccess: (_d, action) => {
      invalidate()
      toast.success(action === 'apply' ? 'Conteo aplicado: el stock quedó actualizado' : 'Conteo cancelado')
    },
    onError,
  })
}
