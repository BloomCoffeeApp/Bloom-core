import { useState } from 'react'

/**
 * True during the render in which any of `deps` differs (Object.is) from the previous render, and
 * (unless `onMount` is false) on the first render. Use it to adjust state when props change — e.g. reset a form when its dialog
 * opens — without a setState-in-effect round trip:
 *
 *   if (useDepsChanged([open]) && open) setForm(initial)
 *
 * See https://react.dev/learn/you-might-not-need-an-effect#adjusting-some-state-when-a-prop-changes
 */
export function useDepsChanged(deps: readonly unknown[], onMount = true): boolean {
  const [prev, setPrev] = useState<readonly unknown[] | null>(onMount ? null : deps)
  const changed = prev === null || prev.length !== deps.length || deps.some((d, i) => !Object.is(d, prev[i]))
  if (changed) setPrev(deps)
  return changed
}
