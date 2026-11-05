import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

import { api } from '@/lib/api'

import { resetPrintingStatus } from './direct'
import type { PrinterCfg, PrintingConfig, PrintingConfigOut, PrintingStatus, PrintResult, WindowsPrinter } from './types'

export const printingKeys = {
  config: ['printing', 'config'] as const,
  status: ['printing', 'status'] as const,
  windows: ['printing', 'windows-printers'] as const,
}

export function usePrintingConfig() {
  return useQuery({ queryKey: printingKeys.config, queryFn: () => api.get<PrintingConfigOut>('/printing/config') })
}

export function usePrintingStatus() {
  return useQuery({
    queryKey: printingKeys.status,
    queryFn: () => api.get<PrintingStatus>('/printing/status'),
    staleTime: 60_000,
    retry: false,
  })
}

export function useWindowsPrinters(enabled: boolean) {
  return useQuery({
    queryKey: printingKeys.windows,
    queryFn: () => api.get<WindowsPrinter[]>('/printing/windows-printers'),
    enabled,
    retry: false,
  })
}

export function useSavePrinting() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (cfg: PrintingConfig) => api.put<PrintingConfigOut>('/printing/config', cfg),
    onSuccess: (cfg) => {
      toast.success('Impresoras guardadas')
      qc.setQueryData(printingKeys.config, cfg)
      qc.invalidateQueries({ queryKey: printingKeys.status })
      resetPrintingStatus()
    },
    onError: (e: Error) => toast.error(e.message),
  })
}

export function useTestPrint() {
  return useMutation({
    mutationFn: (printer: PrinterCfg) => api.post<PrintResult>('/printing/test', { printer }),
    onSuccess: (r) => toast.success(`Se mandó la prueba a «${r.printer}»`),
    onError: (e: Error) => toast.error(e.message),
  })
}
