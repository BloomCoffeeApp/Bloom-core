import { CircleArrowUp } from 'lucide-react'
import { Link } from 'react-router'

import { Button } from '@/components/ui/button'
import { useAuth } from '@/lib/auth'

import { useUpdateStatus } from './api'

export const ABOUT_TAB = '/config?tab=acerca'

/** Subtle header hint for admins when a newer version is published. */
export function UpdateBadge() {
  const { can } = useAuth()
  const { data } = useUpdateStatus(can())
  if (!data?.required && (!data?.available || !data.latest)) return null
  const label = data.required ? 'Actualización obligatoria' : 'Nueva versión'
  return (
    <Button
      variant="ghost"
      size="sm"
      asChild
      className={data.required ? 'gap-1.5 text-destructive hover:text-destructive' : 'gap-1.5 text-primary hover:text-primary'}
    >
      <Link to={ABOUT_TAB} title={data.latest ? `Hay una nueva versión: ${data.latest.version}` : label}>
        <CircleArrowUp />
        <span className="hidden md:inline">{label}</span>
        <span className="sr-only md:hidden">{label}</span>
      </Link>
    </Button>
  )
}
