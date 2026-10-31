import { useEffect, useState } from 'react'

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
  onKeyDown?: React.KeyboardEventHandler<HTMLInputElement>
}) {
  const [text, setText] = useState(toText(value))
  const [focused, setFocused] = useState(false)

  useEffect(() => {
    if (!focused) setText(toText(value))
  }, [value, focused])

  return (
    <div className={cn('relative', className)}>
      <span className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-sm text-muted-foreground">
        $
      </span>
      <Input
        inputMode="decimal"
        className="tabular pl-7"
        value={text}
        onFocus={() => setFocused(true)}
        onBlur={() => {
          setFocused(false)
          setText(toText(value))
        }}
        onChange={(e) => {
          setText(e.target.value)
          onChange(parseMoneyToCents(e.target.value))
        }}
        {...props}
      />
    </div>
  )
}
