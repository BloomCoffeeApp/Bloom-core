import { PackageX } from 'lucide-react'
import { lazy, Suspense, useState } from 'react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

const QuickDiscardDialog = lazy(() => import('./discard').then((m) => ({ default: m.QuickDiscardDialog })))

/** POS / barista: "Descartar" for small spills (se cayó leche, se rompió un vaso…). */
export function QuickDiscardButton({ className, label = true }: { className?: string; label?: boolean }) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <Button
        type="button"
        variant="outline"
        className={cn('h-11', className)}
        onClick={() => setOpen(true)}
        aria-label="Descartar insumo"
        title="Descartar insumo (derrame, rotura…)"
      >
        <PackageX /> {label && 'Descartar'}
      </Button>
      {open && (
        <Suspense fallback={null}>
          <QuickDiscardDialog open={open} onOpenChange={setOpen} />
        </Suspense>
      )}
    </>
  )
}
