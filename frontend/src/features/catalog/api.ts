import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

import { api } from '@/lib/api'

import type {
  BulkPriceResult,
  CategoryInput,
  ModifierGroup,
  ModifierGroupInput,
  PriceHistoryEntry,
  Product,
  ProductCategory,
  ProductInput,
} from './types'

export const catalogKeys = {
  all: ['catalog'] as const,
  products: (includeInactive: boolean) => ['catalog', 'products', includeInactive] as const,
  categories: ['catalog', 'categories'] as const,
  groups: ['catalog', 'modifier-groups'] as const,
  history: (id: number) => ['catalog', 'price-history', id] as const,
}

const onError = (e: Error) => toast.error(e.message)

function useInvalidate() {
  const qc = useQueryClient()
  return () => {
    qc.invalidateQueries({ queryKey: catalogKeys.all })
    // The POS catalog is cached by the POS module under its own key.
    qc.invalidateQueries({ queryKey: ['pos'] })
  }
}

export function useProducts(includeInactive = false) {
  return useQuery({
    queryKey: catalogKeys.products(includeInactive),
    queryFn: () => api.get<Product[]>('/products', { include_inactive: includeInactive || undefined }),
  })
}

export function useProductCategories() {
  return useQuery({ queryKey: catalogKeys.categories, queryFn: () => api.get<ProductCategory[]>('/product-categories') })
}

export function useModifierGroups() {
  return useQuery({ queryKey: catalogKeys.groups, queryFn: () => api.get<ModifierGroup[]>('/modifier-groups') })
}

export function usePriceHistory(id: number | null) {
  return useQuery({
    queryKey: catalogKeys.history(id ?? 0),
    queryFn: () => api.get<PriceHistoryEntry[]>(`/products/${id}/price-history`),
    enabled: id != null,
  })
}

export function useSaveProduct() {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: ({ id, data }: { id?: number; data: Partial<ProductInput> }) =>
      id ? api.patch<Product>(`/products/${id}`, data) : api.post<Product>('/products', data),
    onSuccess: (_d, v) => {
      invalidate()
      toast.success(v.id ? 'Producto actualizado' : 'Producto creado')
    },
    onError,
  })
}

export function useDeactivateProduct() {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: (id: number) => api.delete(`/products/${id}`),
    onSuccess: () => {
      invalidate()
      toast.success('Producto desactivado')
    },
    onError,
  })
}

export function useBulkPrice() {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: (body: { category_id: number | null; percent: number; round_to_cents: number; dry_run: boolean }) =>
      api.post<BulkPriceResult>('/products/bulk-price', body),
    onSuccess: (r) => {
      if (r.applied) {
        invalidate()
        toast.success(`Precios actualizados (${r.items.filter((i) => i.old_cents !== i.new_cents).length} productos)`)
      }
    },
    onError,
  })
}

export function useSaveCategory() {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: ({ id, data }: { id?: number; data: Partial<CategoryInput> }) =>
      id ? api.patch<ProductCategory>(`/product-categories/${id}`, data) : api.post<ProductCategory>('/product-categories', data),
    onSuccess: (_d, v) => {
      invalidate()
      toast.success(v.id ? 'Categoría actualizada' : 'Categoría creada')
    },
    onError,
  })
}

export function useSaveGroup() {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: ({ id, data }: { id?: number; data: ModifierGroupInput }) =>
      id ? api.patch<ModifierGroup>(`/modifier-groups/${id}`, data) : api.post<ModifierGroup>('/modifier-groups', data),
    onSuccess: (_d, v) => {
      invalidate()
      toast.success(v.id ? 'Grupo actualizado' : 'Grupo creado')
    },
    onError,
  })
}

export function useDeleteGroup() {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: (id: number) => api.delete(`/modifier-groups/${id}`),
    onSuccess: () => {
      invalidate()
      toast.success('Grupo eliminado')
    },
    onError,
  })
}
