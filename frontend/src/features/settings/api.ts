import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

import { api, tokenStore } from '@/lib/api'

import { salesKeys } from '../sales/api'

import type {
  AllSettings,
  AuditRow,
  BackupRow,
  PaymentMethod,
  RestoreResult,
  SystemInfo,
  UserCreate,
  UserRow,
  UserUpdate,
} from './types'

const onError = (e: Error) => toast.error(e.message)

export function useSettings() {
  return useQuery({ queryKey: ['settings', 'all'], queryFn: () => api.get<AllSettings>('/settings') })
}

export function useSaveSetting<K extends keyof AllSettings>(key: K, successMsg = 'Cambios guardados') {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (value: AllSettings[K]) => api.put<{ key: K; value: AllSettings[K] }>(`/settings/${key}`, value),
    onSuccess: () => {
      toast.success(successMsg)
      qc.invalidateQueries({ queryKey: ['settings'] })
    },
    onError,
  })
}

export function useUsers(enabled: boolean) {
  return useQuery({ queryKey: ['settings', 'users'], queryFn: () => api.get<UserRow[]>('/users'), enabled })
}

export function useCreateUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: UserCreate) => api.post<UserRow>('/users', data),
    onSuccess: (u) => {
      toast.success(`Usuario ${u.name} creado`)
      qc.invalidateQueries({ queryKey: ['settings', 'users'] })
    },
    onError,
  })
}

export function useUpdateUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: UserUpdate }) => api.patch<UserRow>(`/users/${id}`, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['settings', 'users'] }),
    onError,
  })
}

/** Optional endpoint from the POS/cash module; the tab hides itself if it fails. */
export function usePaymentMethods(enabled: boolean) {
  return useQuery({
    queryKey: ['settings', 'payment-methods'],
    queryFn: () => api.get<PaymentMethod[]>('/payment-methods', { include_inactive: true }),
    retry: false,
    enabled,
  })
}

export function useUpdatePaymentMethod() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...data }: { id: number; active?: boolean; name?: string }) =>
      api.patch<PaymentMethod>(`/payment-methods/${id}`, data),
    onSuccess: (pm) => {
      toast.success(`${pm.name}: ${pm.active ? 'habilitado' : 'deshabilitado'}`)
      qc.invalidateQueries({ queryKey: ['settings', 'payment-methods'] })
      qc.invalidateQueries({ queryKey: salesKeys.methods })
    },
    onError,
  })
}

export function useSystemInfo(enabled: boolean) {
  return useQuery({ queryKey: ['settings', 'system-info'], queryFn: () => api.get<SystemInfo>('/system/info'), enabled })
}

export function useBackups(enabled: boolean) {
  return useQuery({ queryKey: ['settings', 'backups'], queryFn: () => api.get<BackupRow[]>('/system/backups'), enabled })
}

export function useCreateBackup() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => api.post<BackupRow>('/system/backups'),
    onSuccess: () => {
      toast.success('Respaldo creado')
      qc.invalidateQueries({ queryKey: ['settings', 'backups'] })
      qc.invalidateQueries({ queryKey: ['settings', 'system-info'] })
    },
    onError,
  })
}

export function useRestoreBackup() {
  return useMutation({
    mutationFn: (name: string) => api.post<RestoreResult>('/system/restore', { name }),
    onError,
  })
}

export function downloadBackup(name: string) {
  return api.download(`/system/backups/${encodeURIComponent(name)}/download`, undefined, name)
}

export function useAudit(enabled: boolean, limit = 100) {
  return useQuery({
    queryKey: ['settings', 'audit', limit],
    queryFn: () => api.get<AuditRow[]>('/system/audit', { limit }),
    enabled,
  })
}

/** The QR is a protected PNG: fetch it with the token and expose it as an object URL. */
export function useLanQr(enabled: boolean) {
  return useQuery({
    queryKey: ['settings', 'lan-qr'],
    enabled,
    retry: false,
    staleTime: 5 * 60_000,
    queryFn: async () => {
      const token = tokenStore.get()
      const res = await fetch('/api/system/lan-qr', { headers: token ? { Authorization: `Bearer ${token}` } : {} })
      if (!res.ok) throw new Error('No se pudo generar el código QR')
      return URL.createObjectURL(await res.blob())
    },
  })
}

/** QR (protected PNG) pointing to the public customer menu on the LAN address. */
export function useMenuQr(enabled: boolean) {
  return useQuery({
    queryKey: ['settings', 'menu-qr'],
    enabled,
    retry: false,
    staleTime: 5 * 60_000,
    queryFn: async () => {
      const token = tokenStore.get()
      const res = await fetch('/api/system/menu-qr', { headers: token ? { Authorization: `Bearer ${token}` } : {} })
      if (!res.ok) throw new Error('No se pudo generar el código QR')
      return URL.createObjectURL(await res.blob())
    },
  })
}
