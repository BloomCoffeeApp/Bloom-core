import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

import { api, tokenStore } from '@/lib/api'
import { idempotencyKeyFor, releaseIdempotencyKey } from '@/lib/idempotency'

import type {
  Expense,
  ExpenseCategory,
  ExpenseInput,
  ExpenseKind,
  ExpenseList,
  MonthResult,
  RecurringExpense,
  RecurringInput,
} from './types'

export const expenseKeys = {
  all: ['expenses'] as const,
  list: (month: string, f: object) => ['expenses', 'list', month, f] as const,
  categories: ['expenses', 'categories'] as const,
  recurring: ['expenses', 'recurring'] as const,
  summary: (month: string) => ['expenses', 'summary', month] as const,
}

const onError = (e: Error) => toast.error(e.message)

function useInvalidate() {
  const qc = useQueryClient()
  return () => {
    void qc.invalidateQueries({ queryKey: expenseKeys.all })
    void qc.invalidateQueries({ queryKey: ['cash'] }) // a cash expense is an "egreso" of the drawer
    void qc.invalidateQueries({ queryKey: ['alerts'] })
    void qc.invalidateQueries({ queryKey: ['reports'] })
  }
}

export function useExpenses(month: string, filters: { status?: string; category_id?: number; kind?: string } = {}) {
  return useQuery({
    queryKey: expenseKeys.list(month, filters),
    queryFn: () => api.get<ExpenseList>('/expenses', { month, ...filters }),
    placeholderData: keepPreviousData,
  })
}

export function useExpenseCategories() {
  return useQuery({
    queryKey: expenseKeys.categories,
    queryFn: () => api.get<ExpenseCategory[]>('/expenses/categories'),
  })
}

export function useRecurringExpenses() {
  return useQuery({
    queryKey: expenseKeys.recurring,
    queryFn: () => api.get<RecurringExpense[]>('/expenses/recurring'),
  })
}

export function useMonthResult(month: string, enabled = true) {
  return useQuery({
    queryKey: expenseKeys.summary(month),
    queryFn: () => api.get<MonthResult>('/expenses/summary', { month }),
    enabled,
    staleTime: 60_000,
  })
}

export function useSaveExpense() {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: ({ id, body }: { id?: number; body: Partial<ExpenseInput> }) =>
      id ? api.patch<Expense>(`/expenses/${id}`, body) : api.post<Expense>('/expenses', body, { idempotencyKey: idempotencyKeyFor('expense', body) }),
    onSuccess: (_e, v) => {
      if (!v.id) releaseIdempotencyKey('expense')
      invalidate()
      toast.success(v.id ? 'Gasto actualizado' : 'Gasto cargado')
    },
    onError,
  })
}

export function usePayExpense() {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: ({
      id,
      body,
    }: {
      id: number
      body: {
        payment_method?: string | null
        amount_cents?: number
        from_cash?: boolean
      }
    }) => api.post<Expense>(`/expenses/${id}/pay`, body, { idempotencyKey: idempotencyKeyFor(`expense-pay:${id}`, body) }),
    onSuccess: (_e, v) => {
      releaseIdempotencyKey(`expense-pay:${v.id}`)
      invalidate()
      toast.success('Gasto pagado')
    },
    onError,
  })
}

export function useDeleteExpense() {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: (id: number) => api.delete(`/expenses/${id}`),
    onSuccess: () => {
      invalidate()
      toast.success('Gasto borrado')
    },
    onError,
  })
}

export function useReceipt() {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: ({ id, file }: { id: number; file: File | null }) =>
      file ? api.put<Expense>(`/expenses/${id}/receipt`, file) : api.delete<Expense>(`/expenses/${id}/receipt`),
    onSuccess: (_e, v) => {
      invalidate()
      toast.success(v.file ? 'Comprobante guardado' : 'Comprobante quitado')
    },
    onError,
  })
}

/** The receipt photo is private (needs the session): fetched with the token and shown as an object URL. */
export async function fetchReceiptUrl(id: number): Promise<string> {
  const token = tokenStore.get()
  const res = await fetch(`/api/expenses/${id}/receipt`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (!res.ok) throw new Error('No se pudo abrir el comprobante')
  return URL.createObjectURL(await res.blob())
}

export function useSaveRecurring() {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: ({ id, body }: { id?: number; body: Partial<RecurringInput> & { active?: boolean } }) =>
      id ? api.patch(`/expenses/recurring/${id}`, body) : api.post('/expenses/recurring', body),
    onSuccess: (_r, v) => {
      invalidate()
      toast.success(v.id ? 'Gasto fijo actualizado' : 'Gasto fijo creado: se genera solo cada mes')
    },
    onError,
  })
}

export function useSaveCategory() {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: ({ id, body }: { id?: number; body: { name?: string; kind?: ExpenseKind; active?: boolean } }) =>
      id ? api.patch<ExpenseCategory>(`/expenses/categories/${id}`, body) : api.post<ExpenseCategory>('/expenses/categories', body),
    onSuccess: () => invalidate(),
    onError,
  })
}
