import { Download, HardDrive, Loader2, Trash2 } from 'lucide-react'
import { useState } from 'react'

import { ConfirmDialog } from '@/components/confirm-dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

import { Field, SettingsCard } from '../settings/form'
import { useDeleteAccountConfirm, useDeleteAccountStart, useExportAccountData } from './api'

/** Configuración → Cuenta: data rights (Ley 25.326) over what our servers keep about the account. */
export function DataRightsCard({ serverConfigured }: { serverConfigured: boolean }) {
  const exportData = useExportAccountData()
  const start = useDeleteAccountStart()
  const confirm = useDeleteAccountConfirm()
  const [asking, setAsking] = useState(false)
  const [code, setCode] = useState('')
  const sentTo = start.data?.email

  return (
    <SettingsCard
      title="Tus datos"
      description="Qué guardamos sobre tu cuenta y cómo descargarlo o borrarlo."
    >
      <div className="flex items-start gap-3 rounded-xl border p-4" data-testid="local-data-note">
        <HardDrive className="mt-0.5 size-5 shrink-0 text-muted-foreground" />
        <p className="text-sm text-muted-foreground">
          Los datos de tu negocio (ventas, productos, clientes, stock, caja) están <b className="text-foreground">solo
          en esta computadora</b>: no están en nuestros servidores. Los descargás con <b className="text-foreground">
          Configuración → Respaldo</b> y se borran al desinstalar Bloom (y borrar su carpeta de datos).
        </p>
      </div>
      {!serverConfigured ? (
        <p className="text-sm text-muted-foreground">Esta instalación no usa servidor: no guardamos ningún dato tuyo.</p>
      ) : confirm.data?.deleted ? (
        <p className="text-sm" data-testid="account-deleted">
          Eliminamos tu cuenta de nuestros servidores. {confirm.data.retained.join(' ')}
        </p>
      ) : (
        <>
          <p className="text-sm text-muted-foreground">
            En nuestro servidor guardamos tu cuenta (email, negocio, teléfono), tus licencias, computadoras,
            suscripción, cobros, consentimientos y mensajes de contacto.
          </p>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" className="h-9" onClick={() => exportData.mutate()} disabled={exportData.isPending}>
              {exportData.isPending ? <Loader2 className="animate-spin" /> : <Download />}
              Descargar mis datos de la cuenta
            </Button>
            {!sentTo && (
              <Button variant="outline" className="h-9 text-destructive" onClick={() => setAsking(true)} disabled={start.isPending}>
                {start.isPending ? <Loader2 className="animate-spin" /> : <Trash2 />}
                Eliminar mi cuenta
              </Button>
            )}
          </div>
          {sentTo && (
            <form
              className="space-y-3 rounded-xl border border-destructive/40 p-4"
              onSubmit={(e) => {
                e.preventDefault()
                confirm.mutate(code)
              }}
            >
              <Field label={`Código que te mandamos a ${sentTo}`} htmlFor="delete-code" hint="Vence en 15 minutos.">
                <Input
                  id="delete-code"
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  placeholder="123456"
                  className="max-w-40"
                />
              </Field>
              {confirm.error && <p className="text-sm text-destructive">{confirm.error.message}</p>}
              <Button type="submit" variant="destructive" className="h-9" disabled={code.length !== 6 || confirm.isPending}>
                {confirm.isPending && <Loader2 className="animate-spin" />}
                Eliminar definitivamente
              </Button>
            </form>
          )}
        </>
      )}
      <ConfirmDialog
        open={asking}
        onOpenChange={setAsking}
        title="¿Eliminar tu cuenta de Bloom?"
        destructive
        confirmLabel="Enviarme el código"
        onConfirm={() => {
          setAsking(false)
          start.mutate()
        }}
        description={
          <span className="block space-y-2">
            <span className="block">
              Borramos tus datos personales de nuestros servidores, revocamos tus licencias (esta computadora vuelve al
              plan gratis) y despublicamos tu menú online. Si tenés una suscripción activa, cancelala primero.
            </span>
            <span className="block">
              Los cobros se conservan anonimizados el tiempo que exige la ley. Los datos de tu negocio en esta
              computadora no se tocan. Te mandamos un código por mail para confirmar.
            </span>
          </span>
        }
      />
    </SettingsCard>
  )
}
