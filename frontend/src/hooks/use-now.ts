import { useEffect, useState } from 'react'

/** Current time, refreshed every `intervalMs` (keeps "now" out of the render body). */
export function useNow(intervalMs = 60_000) {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), intervalMs)
    return () => clearInterval(t)
  }, [intervalMs])
  return now
}
