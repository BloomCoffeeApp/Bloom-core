import { Gift } from 'lucide-react'

import { Badge } from '@/components/ui/badge'

/** Marks a courtesy sale ("invita la casa"): stock moved, nothing charged. */
export function CourtesyBadge() {
  return (
    <Badge variant="outline" className="border-primary/40 text-primary" data-testid="courtesy-badge">
      <Gift /> Cortesía
    </Badge>
  )
}
