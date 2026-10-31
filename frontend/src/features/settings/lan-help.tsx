import { AlertTriangle, ChevronDown, CircleHelp } from 'lucide-react'

import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'

import type { SystemInfo } from './types'

/** Why a phone/tablet can't open the app over Wi-Fi, and what to check. Shared by LAN mode and the menu QR. */
export function LanHelp({ info }: { info: SystemInfo | undefined }) {
  if (!info) return null
  return (
    <div className="space-y-3">
      {info.network_public && (
        <div className="flex items-start gap-3 rounded-xl border border-warning/50 bg-warning/15 p-3 text-sm" role="alert">
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warning-foreground dark:text-warning" />
          <span>
            <b>Windows marca este Wi-Fi como red pública</b> y bloquea a los otros dispositivos. Cambialo a privada:
            Configuración de Windows → Red e Internet → Wi-Fi → (tu red) → Tipo de perfil de red: <b>Privada</b>.
          </span>
        </div>
      )}
      <Collapsible>
        <CollapsibleTrigger className="group flex min-h-11 items-center gap-2 text-sm font-medium text-muted-foreground hover:text-foreground">
          <CircleHelp className="size-4" />
          ¿No abre en el celular?
          <ChevronDown className="size-4 transition-transform group-data-[state=open]:rotate-180" />
        </CollapsibleTrigger>
        <CollapsibleContent>
          <ul className="mt-1 list-disc space-y-1.5 pl-5 text-sm text-muted-foreground">
            <li>El celular tiene que estar conectado al <b>mismo Wi-Fi</b> que esta computadora (no a los datos móviles).</li>
            <li>Esta computadora tiene que estar prendida y con {info.app_name} abierto.</li>
            <li>
              Si Windows pregunta si permitís que {info.app_name} use la red, elegí <b>Permitir</b> (redes privadas).
            </li>
            <li>El Wi-Fi tiene que estar como red <b>privada</b> en Windows, no pública.</li>
            <li>
              Algunos Wi-Fi de invitados aíslan a los dispositivos entre sí (“aislamiento de clientes”): usá la red
              principal o desactivalo en el router.
            </li>
            <li>Si la dirección cambió (el router le dio otra IP a la PC), volvé a imprimir el QR.</li>
          </ul>
        </CollapsibleContent>
      </Collapsible>
    </div>
  )
}
