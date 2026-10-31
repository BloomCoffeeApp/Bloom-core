import { useNavigate } from 'react-router'

import {
  Command,
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command'
import { useTour } from '@/features/tutorial/use-tour'
import { useAuth } from '@/lib/auth'
import { NAV } from '@/lib/nav'

/** Extra quick actions; modules can add entries here. */
const ACTIONS = [
  { label: 'Nueva venta', to: '/pos', keywords: 'vender cobrar ticket' },
  { label: 'Registrar shot', to: '/barista/shot', keywords: 'espresso extraccion calibrar' },
  { label: 'Cargar compra', to: '/compras?nueva=1', keywords: 'factura proveedor' },
  { label: 'Ajustar stock', to: '/stock', keywords: 'merma inventario' },
  { label: 'Nuevo cliente', to: '/clientes?nuevo=1', keywords: 'cliente fidelizacion' },
]

export function CommandPalette({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const navigate = useNavigate()
  const { can } = useAuth()
  const tour = useTour()
  const go = (to: string) => {
    onOpenChange(false)
    navigate(to)
  }
  const nav = NAV.filter((n) => n.roles.length === 0 || can(...n.roles))
  return (
    <CommandDialog open={open} onOpenChange={onOpenChange} title="Buscar" description="Ir a una sección o acción">
      {/* CommandDialog doesn't provide cmdk's root; without it the input/list throw. */}
      <Command>
        <CommandInput placeholder="Escribí una sección o acción…" />
        <CommandList>
          <CommandEmpty>Sin resultados.</CommandEmpty>
          <CommandGroup heading="Acciones rápidas">
            {ACTIONS.map((a) => (
              <CommandItem key={a.to} value={`${a.label} ${a.keywords}`} onSelect={() => go(a.to)}>
                {a.label}
              </CommandItem>
            ))}
            <CommandItem
              value="Ver tutorial ayuda guia como se usa"
              onSelect={() => {
                onOpenChange(false)
                tour.start()
              }}
            >
              Ver tutorial
            </CommandItem>
          </CommandGroup>
          <CommandGroup heading="Secciones">
            {nav.map((n) => (
              <CommandItem key={n.to} value={n.label} onSelect={() => go(n.to)}>
                <n.icon />
                {n.label}
              </CommandItem>
            ))}
          </CommandGroup>
        </CommandList>
      </Command>
    </CommandDialog>
  )
}
