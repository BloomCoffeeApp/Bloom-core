import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useMemo } from 'react'
import { toast } from 'sonner'

import { api } from '@/lib/api'
import { useAuth } from '@/lib/auth'

import type { BusinessCatalog, BusinessModules, ModuleDef, ModuleKey, ProfileKey } from './types'

export const businessKeys = {
  modules: ['business', 'modules'] as const,
  catalog: ['business', 'catalog'] as const,
}

export function useBusinessModules() {
  const { user } = useAuth()
  return useQuery({
    queryKey: businessKeys.modules,
    queryFn: () => api.get<BusinessModules>('/business/modules'),
    enabled: !!user,
    staleTime: 60_000,
  })
}

/** Profiles and modules without logging in (setup wizard). */
export function useBusinessCatalog() {
  return useQuery({
    queryKey: businessKeys.catalog,
    queryFn: () => api.get<BusinessCatalog>('/business/catalog'),
    staleTime: Infinity,
  })
}

/**
 * Which modules this business type shows. While loading everything counts as shown (same as before
 * profiles existed); `ready` tells when the answer is final (the hidden-module page waits for it).
 */
export function useModules() {
  const q = useBusinessModules()
  const mods = q.data?.modules
  const on = useCallback((key: ModuleKey) => (mods ? mods[key] !== false : true), [mods])
  const ready = q.isSuccess || q.isError
  return useMemo(() => ({ on, ready, data: q.data }), [on, ready, q.data])
}

/** Same rules as the backend `_resolve`: profile defaults + overrides, a module without its requirement is off. */
export function resolveModules(
  catalog: ModuleDef[],
  defaults: Record<ModuleKey, boolean>,
  overrides: Partial<Record<ModuleKey, boolean>>,
): Record<ModuleKey, boolean> {
  const mods = { ...defaults, ...overrides }
  let changed = true
  while (changed) {
    changed = false
    for (const m of catalog) {
      if (mods[m.key] && m.requires.some((r) => !mods[r])) {
        mods[m.key] = false
        changed = true
      }
    }
  }
  return mods
}

export const CHANNEL_MODULES: ModuleKey[] = ['dine_in', 'takeaway', 'delivery']

export function useSaveProfile() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { profile: ProfileKey; modules: Partial<Record<ModuleKey, boolean>> }) =>
      api.put<BusinessModules>('/business/profile', data),
    onSuccess: (data) => {
      qc.setQueryData(businessKeys.modules, data)
      toast.success('Listo, actualizamos las secciones de la app.')
    },
    onError: (e: Error) => toast.error(e.message),
  })
}

export function useSetModule() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ key, enabled }: { key: ModuleKey; enabled: boolean }) =>
      api.put<BusinessModules>(`/business/modules/${key}`, { enabled }),
    onSuccess: (data, v) => {
      qc.setQueryData(businessKeys.modules, data)
      const label = data.catalog.find((m) => m.key === v.key)?.label ?? 'El módulo'
      toast.success(v.enabled ? `${label}: activado.` : `${label}: oculto.`)
    },
    onError: (e: Error) => toast.error(e.message),
  })
}
