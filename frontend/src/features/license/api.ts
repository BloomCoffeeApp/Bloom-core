import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

import { api } from '@/lib/api'

export type ProFeature =
  | 'barista'
  | 'purchases'
  | 'reports'
  | 'exports'
  | 'public_menu'
  | 'lan'
  | 'users'
  | 'backup_export'

/** Mirrors backend app/routers/license.py `_out`. */
export interface LicenseInfo {
  plan: 'free' | 'trial' | 'pro'
  valid: boolean
  features: string[]
  customer: string | null
  license_id: string | null
  perpetual: boolean
  expires_at: number | null
  grace_until: number | null
  in_grace: boolean
  days_left: number | null
  machine_id: string
  problem: string | null
  pro_label: string
  app_name: string
  catalog: Record<ProFeature, string>
  free_max_users: number
  server_configured: boolean
}

export const licenseKey = ['license'] as const

export function useLicense() {
  return useQuery({
    queryKey: licenseKey,
    queryFn: () => api.get<LicenseInfo>('/license'),
    staleTime: 60_000,
    refetchInterval: 15 * 60_000,
  })
}

export function hasFeature(info: LicenseInfo | undefined, feature: ProFeature) {
  return !!info?.valid && (info.features.includes('*') || info.features.includes(feature))
}

/** Undefined while loading (so gates don't flash the upsell). */
export function useHasFeature(feature: ProFeature): boolean | undefined {
  const { data } = useLicense()
  return data ? hasFeature(data, feature) : undefined
}

function useLicenseMutation<T>(fn: (arg: T) => Promise<LicenseInfo>, success: (l: LicenseInfo) => string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: (info) => {
      qc.setQueryData(licenseKey, info)
      // Pro modules may have just become available (or not).
      qc.invalidateQueries({ predicate: (q) => q.queryKey[0] !== 'license' })
      toast.success(success(info))
    },
    onError: (e: Error) => toast.error(e.message),
  })
}

export const useActivateLicense = () =>
  useLicenseMutation((key: string) => api.post<LicenseInfo>('/license/activate', { key }), (l) => `¡Listo! ${l.pro_label} activado.`)

export const useStartTrial = () =>
  useLicenseMutation(() => api.post<LicenseInfo>('/license/trial'), (l) => `Empezó tu prueba de ${l.pro_label}.`)

export const useImportLicense = () =>
  useLicenseMutation((token: string) => api.post<LicenseInfo>('/license/import', { token }), () => 'Licencia importada.')

export const useRefreshLicense = () =>
  useLicenseMutation(() => api.post<LicenseInfo>('/license/refresh'), () => 'Licencia actualizada.')

export const useDeactivateLicense = () =>
  useLicenseMutation(() => api.delete<LicenseInfo>('/license'), () => 'Licencia desactivada en esta computadora.')
