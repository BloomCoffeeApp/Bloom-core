import { Check, Copy, LifeBuoy, Loader2, TriangleAlert } from 'lucide-react'
import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { ApiError } from '@/lib/api'
import { fmtDate } from '@/lib/format'

import { useDiagnosticPreview, useSendDiagnostic } from './api'
import type { Diagnostic } from './types'

const yesNo = (v: boolean | null, yes: string, no: string, unknown = 'Sin datos') => (v === null ? unknown : v ? yes : no)

const LICENSE_STATE: Record<string, string> = {
  active: 'vigente',
  grace: 'en período de gracia',
  invalid: 'con un problema',
  none: 'sin licencia',
}

function rows(d: Diagnostic): [string, string][] {
  return [
    ['Versión de Bloom', d.app_version],
    ['Sistema', d.os],
    ['Base de datos', yesNo(d.db_ok, 'En buen estado', 'Con problemas')],
    ['Tamaño de la base', d.db_size_mb === null ? 'Sin datos' : `${d.db_size_mb} MB`],
    [
      'Último respaldo',
      d.last_backup_at ? `${fmtDate(d.last_backup_at)} (${d.backups ?? 0} guardados)` : 'Todavía no hay respaldos',
    ],
    [
      'Impresora',
      !d.printer?.configured
        ? 'Sin configurar'
        : d.printer.last_ok === null
          ? 'Configurada (todavía no imprimió)'
          : d.printer.last_ok
            ? 'Configurada, la última impresión salió bien'
            : 'Configurada, la última impresión falló',
    ],
    [
      'Licencia',
      d.license ? `${LICENSE_STATE[d.license.state] ?? d.license.state}${d.license.plan ? ` · plan ${d.license.plan}` : ''}` : 'Sin datos',
    ],
    ['Módulos activos', d.modules.length ? d.modules.join(', ') : 'Ninguno'],
    ['Horas encendida', d.uptime_hours === null ? 'Sin datos' : `${d.uptime_hours} h`],
  ]
}

function errorText(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.status === 0 || e.status === 503) return 'No pudimos conectarnos. Revisá tu conexión a internet y probá de nuevo.'
    if (e.status === 429) return 'Ya mandaste varios diagnósticos hace poco. Probá de nuevo más tarde.'
    return e.message
  }
  return 'No se pudo enviar el diagnóstico. Probá de nuevo.'
}

/** Configuración → Acerca de → «Enviar diagnóstico a soporte»: shows exactly what is sent, asks for consent. */
export function DiagnosticDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const preview = useDiagnosticPreview(open)
  const send = useSendDiagnostic()
  const [consent, setConsent] = useState(false)
  const [copied, setCopied] = useState(false)
  const code = send.data?.support_code
  const data = preview.data

  function change(o: boolean) {
    if (!o) {
      setConsent(false)
      setCopied(false)
      send.reset()
    }
    onOpenChange(o)
  }

  function copy() {
    void navigator.clipboard?.writeText(code ?? '')
    setCopied(true)
  }

  return (
    <Dialog open={open} onOpenChange={change}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg" data-testid="diagnostic-dialog">
        <DialogHeader>
          <DialogTitle>Enviar diagnóstico a soporte</DialogTitle>
          <DialogDescription>
            Es un resumen del estado de Bloom en esta computadora, para que podamos ayudarte. Nunca incluye tus
            ventas, clientes, productos ni precios.
          </DialogDescription>
        </DialogHeader>

        {code ? (
          <div className="space-y-3 py-2 text-center" data-testid="diagnostic-sent">
            <p className="text-sm text-muted-foreground">Listo, lo recibimos. Pasale este código a soporte:</p>
            <p className="font-heading text-3xl font-semibold tracking-wider select-all" data-testid="support-code">
              {code}
            </p>
            <Button variant="outline" className="min-h-11" onClick={copy}>
              {copied ? <Check className="size-4" /> : <Copy className="size-4" />} {copied ? 'Copiado' : 'Copiar'}
            </Button>
          </div>
        ) : preview.isLoading ? (
          <p className="flex items-center gap-2 py-6 text-sm text-muted-foreground" role="status">
            <Loader2 className="size-4 animate-spin" /> Armando el resumen…
          </p>
        ) : preview.isError || !data ? (
          <p className="py-4 text-sm text-destructive" role="alert">
            No pudimos armar el resumen. Probá de nuevo en un momento.
          </p>
        ) : (
          <div className="space-y-4">
            {!data.available && (
              <p className="flex items-start gap-2 rounded-lg border p-3 text-sm" role="status" data-testid="diagnostic-unavailable">
                <TriangleAlert className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
                {data.reason ?? 'El envío de diagnósticos no está disponible en esta instalación.'}
              </p>
            )}
            <dl className="divide-y rounded-lg border text-sm" data-testid="diagnostic-summary">
              {rows(data.diagnostic).map(([k, v]) => (
                <div key={k} className="flex flex-col gap-0.5 px-3 py-2 sm:flex-row sm:justify-between sm:gap-4">
                  <dt className="text-muted-foreground">{k}</dt>
                  <dd className="font-medium sm:text-right">{v}</dd>
                </div>
              ))}
            </dl>
            <div>
              <p className="mb-1.5 text-sm font-medium">Últimos errores (24 h): {data.diagnostic.errors.length}</p>
              {data.diagnostic.errors.length === 0 ? (
                <p className="text-sm text-muted-foreground">No hubo errores registrados.</p>
              ) : (
                <ul className="max-h-40 space-y-1 overflow-y-auto rounded-lg border p-2 text-xs" data-testid="diagnostic-errors">
                  {data.diagnostic.errors.map((e, i) => (
                    <li key={i} className="break-words">
                      <span className="text-muted-foreground">{e.ts}</span> {e.kind}: {e.message}
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <p className="text-xs text-muted-foreground">
              Se envía además un identificador anónimo de esta computadora
              {data.includes_license ? ' y tu licencia, para que soporte sepa de quién es' : ' (sin tu licencia: es anónimo)'}.
              Lo guardamos 30 días y se borra solo.
            </p>
            {data.available && (
              <div className="flex min-h-11 items-start gap-2.5">
                <Checkbox
                  id="diag-consent"
                  checked={consent}
                  onCheckedChange={(v) => setConsent(v === true)}
                  className="mt-0.5"
                />
                <Label htmlFor="diag-consent" className="leading-snug font-normal">
                  Entiendo qué se envía y quiero mandar este diagnóstico a soporte.
                </Label>
              </div>
            )}
            {send.isError && (
              <p className="text-sm text-destructive" role="alert" data-testid="diagnostic-error">
                {errorText(send.error)}
              </p>
            )}
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" className="min-h-11" onClick={() => change(false)}>
            {code ? 'Cerrar' : 'Cancelar'}
          </Button>
          {!code && data?.available && (
            <Button className="min-h-11" disabled={!consent || send.isPending} onClick={() => send.mutate()}>
              {send.isPending ? <Loader2 className="size-4 animate-spin" /> : <LifeBuoy className="size-4" />}
              {send.isPending ? 'Enviando…' : 'Enviar'}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
