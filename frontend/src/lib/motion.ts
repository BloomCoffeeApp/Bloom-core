import { useState } from 'react'

/**
 * Brief "bump" when a value changes (not on the first render), CSS only.
 * Put `key={bump.key}` and `className={bump.className}` on the element showing the value:
 * each change remounts it and its `motion-bump` animation plays once.
 * Honors `prefers-reduced-motion` through the global guard in `index.css`.
 */
export function useBump(value: unknown, className = 'motion-bump'): { key: number; className: string } {
  const [prev, setPrev] = useState(value)
  const [count, setCount] = useState(0)
  if (!Object.is(prev, value)) {
    setPrev(value)
    setCount((c) => c + 1)
  }
  return { key: count, className: count > 0 ? className : '' }
}
