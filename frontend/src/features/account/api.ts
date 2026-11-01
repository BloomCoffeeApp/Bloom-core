import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

import { api } from '@/lib/api'

import { licenseKey } from '../license/api'
import type { AccountInfo, EmailPreferences, LinkConfirmResult } from './types'

export const accountKey = ['account'] as const
export const emailPrefsKey = ['account', 'preferences'] as const

export function useAccount() {
  return useQuery({ queryKey: accountKey, queryFn: () => api.get<AccountInfo>('/account') })
}

export function useLinkStart() {
  return useMutation({
    mutationFn: (body: { email: string; name?: string; accept_terms: boolean; marketing_opt_in?: boolean; product_updates_opt_in?: boolean }) =>
      api.post<{ ok: boolean; message: string; expires_in: number }>('/account/link/start', body),
  })
}

const TRIAL_MESSAGES: Record<string, string> = {
  started: 'Empezó tu prueba gratis de Pro.',
  existing: 'Tu prueba gratis sigue activa.',
  used: 'Esta cuenta o esta computadora ya usó su prueba gratis.',
}

export function useLinkConfirm() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { email: string; code: string }) => api.post<LinkConfirmResult>('/account/link/confirm', body),
    onSuccess: (r) => {
      qc.setQueryData(accountKey, { linked: r.linked, account: r.account, server_configured: r.server_configured })
      void qc.invalidateQueries({ queryKey: emailPrefsKey })
      const extra = r.trial_started ? ` ${TRIAL_MESSAGES.started}` : r.trial_status === 'used' ? ` ${TRIAL_MESSAGES.used}` : ''
      toast.success(`Computadora vinculada a tu cuenta.${extra}`)
      if (r.trial_started) void qc.invalidateQueries({ queryKey: licenseKey })
    },
  })
}

export function useUnlink() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => api.delete<AccountInfo>('/account'),
    onSuccess: (info) => {
      qc.setQueryData(accountKey, info)
      void qc.invalidateQueries({ queryKey: emailPrefsKey })
      toast.success('Desvinculaste esta computadora de la cuenta.')
    },
  })
}

export function useEmailPreferences(enabled = true) {
  return useQuery({
    queryKey: emailPrefsKey,
    queryFn: () => api.get<EmailPreferences>('/account/preferences'),
    enabled,
    staleTime: 30_000,
    retry: false,
  })
}

export function useSaveEmailPreferences() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { news?: boolean; updates?: boolean }) => api.put<EmailPreferences>('/account/preferences', body),
    onSuccess: (prefs) => {
      qc.setQueryData(emailPrefsKey, prefs)
      toast.success('Preferencias de mails guardadas.')
    },
    onError: (e: Error) => toast.error(e.message),
  })
}
