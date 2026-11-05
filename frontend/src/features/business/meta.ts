import type { ModuleDef, ModuleKey } from './types'

export type Overrides = Partial<Record<ModuleKey, boolean>>

/** Turning a module on also turns on what it needs (same as the backend's "Activarlo"). */
export function toggleOverride(catalog: ModuleDef[], overrides: Overrides, key: ModuleKey, on: boolean): Overrides {
  const next = { ...overrides, [key]: on }
  if (on) for (const r of catalog.find((m) => m.key === key)?.requires ?? []) next[r] = true
  return next
}
