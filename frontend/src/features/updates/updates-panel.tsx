import { CircleArrowUp, CircleCheck, CircleAlert, Loader2, RefreshCw } from 'lucide-react'
import { useState } from 'react'

import { ConfirmDialog } from '@/components/confirm-dialog'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { fmtDate, fmtNumber, fmtRelative } from '@/lib/format'

import { useCheckUpdates, useInstallUpdate, useUpdateStatus } from './api'
import type { UpdateStatus } from './types'

const mb = (bytes: number) => `${fmtNumber(bytes / 1024 ** 2, 1)} MB`

function Working({ status }: { status: UpdateStatus }) {
  const { downloaded, total } = status.progress
  const pct = total ? Math.min(100, Math.round((downloaded / total) * 100)) : 0
  if (status.state === 'downloading') {
    return (
      <div className="space-y-2" role="status">
        <p className="text-sm">
          Descargando la actualización… {pct}% <span className="text-muted-foreground">({mb(downloaded)} de {mb(total)})</span>
        </p>
        <Progress value={pct} aria-label="Progreso de la descarga" />
      </div>
    )
  }
  const text =
    status.state === 'verifying'
      ? 'Verificando la descarga y haciendo un respaldo de tus datos…'
      : (status.message ?? 'Instalando la actualización…')
  return (
    <p className="flex items-center gap-2 text-sm" role="status">
      <Loader2 className="size-4 animate-spin text-muted-foreground" /> {text}
    </p>
  )
}

/** Configuración → Acerca de: version check and one-click update (admins). */
export function UpdatesPanel() {
  const { data: status, isLoading } = useUpdateStatus(true)
  const check = useCheckUpdates()
  const install = useInstallUpdate()
  const [confirming, setConfirming] = useState(false)

  if (isLoading || !status) return null
  const checking = check.isPending || status.state === 'checking'
  const busy = ['downloading', 'verifying', 'installing'].includes(status.state)
  const latest = status.latest

  return (
    <div className="space-y-3 rounded-xl border p-4" data-testid="updates-panel">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="text-sm">
          <p className="font-medium">Actualizaciones</p>
          <p className="text-muted-foreground">
            {status.configured
              ? status.checked_at
                ? `Última búsqueda ${fmtRelative(status.checked_at)}.`
                : 'La app busca versiones nuevas sola cada algunas horas.'
              : 'Esta instalación no tiene configuradas las actualizaciones automáticas.'}
          </p>
        </div>
        {status.configured && (
          <Button variant="outline" onClick={() => check.mutate()} disabled={checking || busy}>
            {checking ? <Loader2 className="animate-spin" /> : <RefreshCw />}
            Buscar actualizaciones
          </Button>
        )}
      </div>

      {status.error && !busy && (
        <p className="flex items-start gap-2 text-sm text-destructive">
          <CircleAlert className="mt-0.5 size-4 shrink-0" /> {status.error}
        </p>
      )}

      {status.configured && !latest && !status.error && status.checked_at && !checking && (
        <p className="flex items-center gap-2 text-sm">
          <CircleCheck className="size-4 text-success" /> Estás al día: tenés la última versión ({status.current_version}).
        </p>
      )}

      {latest && (
        <div className="space-y-3 rounded-lg bg-primary/5 p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="flex items-center gap-2 font-medium">
              <CircleArrowUp className="size-4 text-primary" /> Nueva versión {latest.version} disponible
            </p>
            <p className="text-xs text-muted-foreground">
              {latest.published_at && `Publicada el ${fmtDate(latest.published_at)} · `}
              {mb(latest.size)}
            </p>
          </div>
          {latest.notes && <p className="text-sm whitespace-pre-line text-muted-foreground">{latest.notes}</p>}
          {busy ? (
            <Working status={status} />
          ) : status.state === 'ready' ? (
            <p className="text-sm text-muted-foreground" role="status">
              {status.message}
            </p>
          ) : (
            <Button onClick={() => setConfirming(true)} disabled={install.isPending}>
              <CircleArrowUp /> Actualizar ahora
            </Button>
          )}
        </div>
      )}

      <ConfirmDialog
        open={confirming}
        onOpenChange={setConfirming}
        title={`¿Actualizar a la versión ${latest?.version ?? ''}?`}
        description="Se descarga la actualización, se hace un respaldo de tus datos y la aplicación se va a cerrar y volver a abrir sola en unos segundos. Tus datos no se tocan."
        confirmLabel="Actualizar"
        onConfirm={() => install.mutate()}
      />
    </div>
  )
}
