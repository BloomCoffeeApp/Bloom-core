import { useState } from 'react'

import { Input } from '@/components/ui/input'
import { parseMoneyToCents } from '@/lib/format'
import { cn } from '@/lib/utils'

const toText = (cents: number | null | undefined) =>
  cents == null ? '' : (cents / 100).toLocaleString('es-AR', { maximumFractionDigits: 2 })

/** Money input that edits pesos as text and emits integer cents. */
export function MoneyInput({
  value,
  onChange,
  className,
  ...props
}: {
  value: number | null | undefined
  onChange: (cents: number | null) => void
  className?: string
  placeholder?: string
  autoFocus?: boolean
  disabled?: boolean
  id?: string
  'aria-label'?: string
  onKeyDown?: React.KeyboardEventHandler<HTMLInputElement>
}) {
  // While focused the user edits free text; otherwise the field always shows the formatted value.
  const [text, setText] = useState(() => toText(value))
  const [focused, setFocused] = useState(false)

  return (
    <div className={cn('relative', className)}>
      <span className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-sm text-muted-foreground">
        $
      </span>
      <Input
        inputMode="decimal"
        className="tabular pl-7"
        value={focused ? text : toText(value)}
        onFocus={() => {
          setText(toText(value))
          setFocused(true)
        }}
        onBlur={() => setFocused(false)}
        onChange={(e) => {
          setText(e.target.value)
          setFocused(true)
          onChange(parseMoneyToCents(e.target.value))
        }}
        {...props}
      />
    </div>
  )
}
