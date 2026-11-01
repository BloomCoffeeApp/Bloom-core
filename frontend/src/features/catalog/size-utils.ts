import type { ProductSize, ProductSizeInput, Size } from './types'

/** Editor draft of one size row (every catalog size gets a row; `enabled` = sold in it). */
export interface SizeDraft {
  size_id: number
  enabled: boolean
  price: number | null
  scale: string
  /** stock_item_id → qty text. Replaces the scaled base qty ("0" = not used in this size). */
  overrides: Record<number, string>
}

export const num = (s: string) => {
  const n = Number(s.replace(',', '.'))
  return Number.isFinite(n) ? n : 0
}

const fmtQty = (n: number) => String(Math.round(n * 100) / 100)

export function draftsFor(sizes: Size[], product: { sizes: ProductSize[] } | null): SizeDraft[] {
  const linked = new Map(product?.sizes.map((s) => [s.size_id, s]))
  return sizes
    .filter((s) => s.active || linked.has(s.id))
    .map((s) => {
      const ps = linked.get(s.id)
      return {
        size_id: s.id,
        enabled: !!ps,
        price: ps?.price_cents ?? null,
        scale: fmtQty(ps?.recipe_scale ?? 1),
        overrides: Object.fromEntries((ps?.recipe_overrides ?? []).map((o) => [o.stock_item_id, fmtQty(o.qty)])),
      }
    })
}

/** Same rule as backend recipes.size_recipe: base × scale, then overrides replace. */
export function effectiveRecipe(base: Map<number, number>, d: SizeDraft): Map<number, number> {
  const scale = num(d.scale) || 1
  const out = new Map<number, number>()
  for (const [sid, qty] of base) out.set(sid, qty * scale)
  for (const [sid, q] of Object.entries(d.overrides)) out.set(Number(sid), num(q))
  for (const [sid, q] of out) if (Math.abs(q) < 1e-9) out.delete(sid)
  return out
}

export function toInput(drafts: SizeDraft[], defaultId: number | null): ProductSizeInput[] {
  return drafts
    .filter((d) => d.enabled)
    .map((d) => ({
      size_id: d.size_id,
      price_cents: d.price ?? 0,
      recipe_scale: num(d.scale) > 0 ? num(d.scale) : 1,
      is_default: d.size_id === defaultId,
      recipe_overrides: Object.entries(d.overrides)
        .filter(([, q]) => q.trim() !== '' && num(q) >= 0)
        .map(([sid, q]) => ({ stock_item_id: Number(sid), qty: num(q) })),
    }))
}

export const fmtScale = (s: string) => `×${fmtQty(num(s) || 1).replace('.', ',')}`
export { fmtQty }
