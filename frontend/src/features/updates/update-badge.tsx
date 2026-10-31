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
  if (!data?.available || !data.latest) return null
  return (
    <Button variant="ghost" size="sm" asChild className="gap-1.5 text-primary hover:text-primary">
      <Link to={ABOUT_TAB} title={`Hay una nueva versión: ${data.latest.version}`}>
        <CircleArrowUp />
        <span className="hidden md:inline">Nueva versión</span>
        <span className="sr-only md:hidden">Nueva versión disponible</span>
      </Link>
    </Button>
  )
}
