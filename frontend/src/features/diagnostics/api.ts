import { useMutation, useQuery } from '@tanstack/react-query'

import { api } from '@/lib/api'

import type { DiagnosticPreview, DiagnosticSent } from './types'

/** Admin only. Fetched each time the dialog opens: it must show what would be sent right now. */
export function useDiagnosticPreview(enabled: boolean) {
  return useQuery({
    queryKey: ['diagnostics', 'preview'],
    queryFn: () => api.get<DiagnosticPreview>('/diagnostics/preview'),
    enabled,
    retry: false,
    gcTime: 0,
    staleTime: 0,
  })
}

export function useSendDiagnostic() {
  return useMutation({
    mutationFn: () => api.post<DiagnosticSent>('/diagnostics/send', { consent: true }),
  })
}
