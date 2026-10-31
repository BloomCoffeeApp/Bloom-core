import { Loader2, Save } from 'lucide-react'
import type { ReactNode } from 'react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle, CardAction } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

export function SettingsCard({
  title,
  description,
  children,
  onSave,
  saving,
  dirty = true,
  action,
  footer,
  className,
}: {
  title: string
  description?: ReactNode
  children: ReactNode
  onSave?: () => void
  saving?: boolean
  dirty?: boolean
  action?: ReactNode
  footer?: ReactNode
  className?: string
}) {
  return (
    <Card className={cn('rounded-2xl', className)}>
      <CardHeader>
        <CardTitle className="font-heading text-lg">{title}</CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
        {action && <CardAction>{action}</CardAction>}
      </CardHeader>
      <CardContent className="space-y-5">{children}</CardContent>
      {(onSave || footer) && (
        <CardFooter className="justify-end gap-2 border-t pt-4">
          {footer}
          {onSave && (
            <Button onClick={onSave} disabled={saving || !dirty} className="h-9 px-4">
              {saving ? <Loader2 className="animate-spin" /> : <Save />}
              Guardar
            </Button>
          )}
        </CardFooter>
      )}
    </Card>
  )
}

export function Field({
  label,
  hint,
  htmlFor,
  children,
  className,
}: {
  label: string
  hint?: ReactNode
  htmlFor?: string
  children: ReactNode
  className?: string
}) {
  return (
    <div className={cn('space-y-1.5', className)}>
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  )
}

export function NumberInput({
  id,
  value,
  onChange,
  min,
  max,
  step = 1,
  suffix,
  className,
}: {
  id?: string
  value: number
  onChange: (v: number) => void
  min?: number
  max?: number
  step?: number
  suffix?: string
  className?: string
}) {
  return (
    <div className={cn('relative', className)}>
      <Input
        id={id}
        type="number"
        inputMode="numeric"
        value={Number.isFinite(value) ? value : ''}
        min={min}
        max={max}
        step={step}
        onChange={(e) => onChange(e.target.value === '' ? Number.NaN : Number(e.target.value))}
        className={cn('tabular', suffix && 'pr-14')}
      />
      {suffix && (
        <span className="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 text-xs text-muted-foreground">{suffix}</span>
      )}
    </div>
  )
}

export function SwitchRow({
  title,
  description,
  control,
}: {
  title: string
  description?: ReactNode
  control: ReactNode
}) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-xl border p-4">
      <div className="min-w-0">
        <p className="font-medium">{title}</p>
        {description && <p className="text-sm text-muted-foreground">{description}</p>}
      </div>
      {control}
    </div>
  )
}

export function CardSkeleton() {
  return (
    <Card className="rounded-2xl">
      <CardContent className="space-y-4 py-6">
        <Skeleton className="h-6 w-48" />
        <Skeleton className="h-9 w-full" />
        <Skeleton className="h-9 w-full" />
        <Skeleton className="h-9 w-2/3" />
      </CardContent>
    </Card>
  )
}

/** Validates that every value is a finite number within [min, max]. */
export function validNumbers(values: [number, number, number][]) {
  return values.every(([v, min, max]) => Number.isFinite(v) && v >= min && v <= max)
}
