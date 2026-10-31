import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

import { useHasFeature } from '@/features/license/api'
import { api } from '@/lib/api'

/** What Stock needs from the Compras (Pro) module; inert when it isn't licensed. */
export interface SupplierLite {
  id: number
  name: string
  active: boolean
}

export function useSuppliersLite(enabled = true) {
  const pro = useHasFeature('purchases')
  return useQuery({
    // Same key as the Compras module, so both stay in sync.
    queryKey: ['purchases', 'suppliers', false],
    queryFn: () => api.get<SupplierLite[]>('/suppliers'),
    enabled: enabled && !!pro,
  })
}

export function useCreateOrderFromSuggestions() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (supplierId: number) =>
      api.post<{ id: number }>('/purchase-orders/from-suggestions', { supplier_id: supplierId }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['purchases'] })
      toast.success('Borrador de orden creado')
    },
    onError: (e: Error) => toast.error(e.message),
  })
}
