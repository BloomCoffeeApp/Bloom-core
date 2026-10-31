import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

import { useHasFeature } from '@/features/license/api'
import { api } from '@/lib/api'
import { proModules } from '@pro'

/** What Stock needs from the Compras (Pro) module; inert when it isn't licensed. */
export interface SupplierLite {
  id: number
  name: string
  active: boolean
}

export function useSuppliersLite(enabled = true) {
  // Only when the Compras module is in this build (Pro edition) and licensed.
  const licensed = useHasFeature('purchases')
  const pro = !!proModules.Purchases && licensed
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
