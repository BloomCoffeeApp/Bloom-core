import { toast } from 'sonner'

import { api, ApiError } from '@/lib/api'

import type { PrintingStatus, PrintResult } from './types'

/**
 * Direct (ESC/POS) printing with fallback: when there's no cashier printer, direct printing isn't
 * available (demo, not Windows) or the printer fails, the caller opens the system print dialog
 * (the HTML documents) — failures also show a clear message.
 */
let cached: { at: number; value: Promise<PrintingStatus | null> } | null = null

export function resetPrintingStatus() {
  cached = null
}

export function printingStatus(): Promise<PrintingStatus | null> {
  if (!cached || Date.now() - cached.at > 30_000) {
    cached = { at: Date.now(), value: api.get<PrintingStatus>('/printing/status').catch(() => null) }
  }
  return cached.value
}

const FALLBACK = 'Se abrió el diálogo de impresión del sistema.'

/** true = printed on the thermal printer; false = use the print dialog. */
export async function printDirect(path: string, body: unknown = {}): Promise<boolean> {
  const st = await printingStatus()
  if (!st?.cashier) return false
  try {
    await api.post<PrintResult>(path, body)
    return true
  } catch (e) {
    if (e instanceof ApiError && e.status === 409) {
      // The configuration changed meanwhile (or printing got disabled): quietly use the dialog.
      resetPrintingStatus()
      return false
    }
    toast.error(`${(e as Error).message}. ${FALLBACK}`, { duration: 8000 })
    return false
  }
}

/** Right after a sale: prints the ticket when the mode is "automático" and opens the cash drawer. */
export async function afterSale(sale: { id: number; is_courtesy: boolean; payments: { method: string; amount_cents: number }[] }, fallback: () => void) {
  const st = await printingStatus()
  const cash = !sale.is_courtesy && sale.payments.some((p) => p.method === 'efectivo' && p.amount_cents > 0)
  if (st?.ticket_mode === 'auto') {
    if (!(await printDirect(`/printing/sales/${sale.id}/ticket`, { open_drawer: true }))) fallback()
    return
  }
  if (st?.cash_drawer && cash) {
    try {
      await api.post<PrintResult>(`/printing/sales/${sale.id}/drawer`)
    } catch (e) {
      toast.error(`No se pudo abrir el cajón: ${(e as Error).message}`)
    }
  }
}
