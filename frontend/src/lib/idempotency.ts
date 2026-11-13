/**
 * Idempotency keys for requests that move money (sales, cash movements, account payments).
 *
 * The server registers an operation ONCE per key, so the same request sent twice (double click, retry after a
 * timeout or a flaky Wi-Fi) is not done twice. The rule here: a retry of the SAME request reuses its key; a
 * different request (or the next one after a success) gets a fresh key.
 */
const last = new Map<string, { json: string; key: string }>()

/** 128 random bits as hex. `crypto.randomUUID()` only exists on https/localhost; tablets use http on the LAN. */
export function newIdempotencyKey(): string {
  const bytes = new Uint8Array(16)
  crypto.getRandomValues(bytes)
  return Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('')
}

/** The key for `body` under `scope`: unchanged while the same request is retried, new when the request changes. */
export function idempotencyKeyFor(scope: string, body: unknown): string {
  const json = JSON.stringify(body)
  const prev = last.get(scope)
  if (prev && prev.json === json) return prev.key
  const key = newIdempotencyKey()
  last.set(scope, { json, key })
  return key
}

/** Call it when the operation succeeded: the next identical request is a NEW operation (another coffee, same price). */
export function releaseIdempotencyKey(scope: string) {
  last.delete(scope)
}
