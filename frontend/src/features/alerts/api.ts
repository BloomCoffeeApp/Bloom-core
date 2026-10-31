import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

import { api } from '@/lib/api'

import type {
  Alert,
  AlertFilter,
  AlertSummary,
  Checklist,
  ChecklistInput,
  ChecklistRun,
  Notice,
  NoticeInput,
} from './types'

// The app header polls ['alerts', 'summary']; every alerts key shares the 'alerts' prefix.
export const alertKeys = {
  all: ['alerts'] as const,
  list: (status: AlertFilter) => ['alerts', 'list', status] as const,
  summary: ['alerts', 'summary'] as const,
  notices: (includeExpired: boolean) => ['alerts', 'notices', includeExpired] as const,
  checklists: ['alerts', 'checklists'] as const,
  today: ['alerts', 'checklists', 'today'] as const,
}

const onError = (e: Error) => toast.error(e.message)

export function useAlerts(status: AlertFilter) {
  return useQuery({
    queryKey: alertKeys.list(status),
    queryFn: () => api.get<Alert[]>('/alerts', { status }),
    refetchInterval: 60_000,
  })
}

export function useAlertSummary() {
  return useQuery({ queryKey: alertKeys.summary, queryFn: () => api.get<AlertSummary>('/alerts/summary') })
}

function useAlertsMutation<V>(fn: (v: V) => Promise<unknown>, success?: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['alerts', 'list'] })
      qc.invalidateQueries({ queryKey: alertKeys.summary })
      if (success) toast.success(success)
    },
    onError,
  })
}

export const useReadAlert = () => useAlertsMutation((id: number) => api.post<Alert>(`/alerts/${id}/read`))
export const useResolveAlert = () =>
  useAlertsMutation((id: number) => api.post<Alert>(`/alerts/${id}/resolve`), 'Alerta resuelta')
export const useReadAll = () =>
  useAlertsMutation(() => api.post<AlertSummary>('/alerts/read-all'), 'Todas marcadas como leídas')

export function useRefreshAlerts() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => api.post<AlertSummary>('/alerts/refresh'),
    onSuccess: (s) => {
      qc.setQueryData(alertKeys.summary, s)
      qc.invalidateQueries({ queryKey: ['alerts', 'list'] })
      toast.success(s.open ? `Revisado: ${s.open} ${s.open === 1 ? 'alerta abierta' : 'alertas abiertas'}` : 'Revisado: todo en orden')
    },
    onError,
  })
}

// ---------------------------------------------------------------- notices

export function useNotices(includeExpired = false) {
  return useQuery({
    queryKey: alertKeys.notices(includeExpired),
    queryFn: () => api.get<Notice[]>('/notices', { include_expired: includeExpired || undefined }),
  })
}

export function useSaveNotice() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id?: number; data: Partial<NoticeInput> }) =>
      id ? api.patch<Notice>(`/notices/${id}`, data) : api.post<Notice>('/notices', data),
    onSuccess: (_n, vars) => {
      qc.invalidateQueries({ queryKey: ['alerts', 'notices'] })
      if (vars.data.title !== undefined) toast.success(vars.id ? 'Aviso actualizado' : 'Aviso publicado')
    },
    onError,
  })
}

export function useDeleteNotice() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => api.delete(`/notices/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['alerts', 'notices'] })
      toast.success('Aviso eliminado')
    },
    onError,
  })
}

// ---------------------------------------------------------------- checklists

export function useChecklistsToday() {
  return useQuery({ queryKey: alertKeys.today, queryFn: () => api.get<ChecklistRun[]>('/checklists/today') })
}

export function useChecklists(enabled = true) {
  return useQuery({
    queryKey: alertKeys.checklists,
    queryFn: () => api.get<Checklist[]>('/checklists'),
    enabled,
  })
}

export function useToggleRunItem() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ run, itemId, done }: { run: ChecklistRun; itemId: number; done: boolean }) => {
      let runId = run.run_id
      if (runId == null) {
        const started = await api.post<ChecklistRun>(`/checklists/${run.checklist_id}/runs`)
        runId = started.run_id!
      }
      return api.patch<ChecklistRun>(`/checklist-runs/${runId}/items/${itemId}`, { done })
    },
    onSuccess: (updated, vars) => {
      qc.setQueryData<ChecklistRun[]>(alertKeys.today, (old) =>
        old?.map((r) => (r.checklist_id === updated.checklist_id ? updated : r)),
      )
      if (updated.completed_at && !vars.run.completed_at) toast.success(`¡${updated.name} completo!`)
    },
    onError,
  })
}

export function useSaveChecklist() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id?: number; data: Partial<ChecklistInput> }) =>
      id ? api.patch<Checklist>(`/checklists/${id}`, data) : api.post<Checklist>('/checklists', data),
    onSuccess: (_c, vars) => {
      qc.invalidateQueries({ queryKey: alertKeys.checklists })
      toast.success(vars.id ? 'Checklist actualizado' : 'Checklist creado')
    },
    onError,
  })
}
