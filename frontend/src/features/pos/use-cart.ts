import { useCallback, useEffect, useMemo, useState } from 'react'

import type { PosConfig, CartLine, CartState, PosCustomer, PosModifier, PosProduct, PosSize, QuoteLine } from './types'
import type { Channel } from '../sales/types'
import type { Tab } from '../orders/types'

const KEY = 'pos.cart.v2' // v2: lines carry the chosen size

const EMPTY: CartState = {
  lines: [],
  channel: 'salon',
  table_label: '',
  customer: null,
  discount: { mode: 'amount', value: 0 },
  points_to_redeem: 0,
  tab: null,
  reward: null,
}

function load(): CartState {
  try {
    const raw = sessionStorage.getItem(KEY)
    if (!raw) return EMPTY
    const parsed = JSON.parse(raw) as Partial<CartState>
    return { ...EMPTY, ...parsed, lines: Array.isArray(parsed.lines) ? parsed.lines : [] }
  } catch {
    return EMPTY
  }
}

const lineKey = (productId: number, sizeId: number | null, mods: PosModifier[], notes: string) =>
  `${productId}|${sizeId ?? ''}|${mods.map((m) => m.id).sort((a, b) => a - b).join(',')}|${notes.trim().toLowerCase()}`

export interface CartTotals {
  subtotal: number
  discount: number
  pointsDiscount: number
  /** Automatic promotions (already inside subtotal; shown as savings). */
  promoDiscount: number
  /** Stamp-card discount reward. */
  rewardDiscount: number
  total: number
  items: number
  pointsEarned: number
}

/** Net of a cart line: reward lines are free; promotions come from the backend quote. */
export function lineNet(l: CartLine, promo?: QuoteLine) {
  if (l.reward) return 0
  const gross = Math.round(l.unit_cents * l.qty)
  return Math.max(gross - l.discount_cents - Math.min(promo?.discount_cents ?? 0, gross - l.discount_cents), 0)
}

/** Preview only: mirrors backend math (the backend always recalculates and validates). */
export function computeTotals(cart: CartState, cfg?: PosConfig, quote?: QuoteLine[]): CartTotals {
  const promoOf = (i: number) => quote?.find((q) => q.index === i)
  const subtotal = cart.lines.reduce((a, l, i) => a + lineNet(l, promoOf(i)), 0)
  const promoDiscount = cart.lines.reduce(
    (a, l, i) => a + (l.reward ? 0 : Math.round(l.unit_cents * l.qty) - l.discount_cents - lineNet(l, promoOf(i))),
    0,
  )
  const raw = cart.discount.mode === 'pct' ? Math.round((subtotal * cart.discount.value) / 100) : cart.discount.value
  const discount = Math.min(Math.max(raw, 0), subtotal)
  const ppr = cfg?.loyalty.points_per_reward ?? 0
  const rewardValue = cfg?.loyalty.reward_value_cents ?? 0
  const pointsDiscount =
    cart.points_to_redeem && ppr > 0
      ? Math.min(Math.floor(cart.points_to_redeem / ppr) * rewardValue, subtotal - discount)
      : 0
  const left = subtotal - discount - pointsDiscount
  const r = cart.reward
  const rewardDiscount = r ? Math.min(r.kind === 'pct' ? Math.round((left * Math.min(r.value, 100)) / 100) : r.value, left) : 0
  const total = left - rewardDiscount
  const ppp = cfg?.loyalty.enabled ? cfg.loyalty.pesos_per_point : 0
  return {
    subtotal,
    discount,
    pointsDiscount,
    promoDiscount,
    rewardDiscount,
    total,
    items: cart.lines.reduce((a, l) => a + l.qty, 0),
    pointsEarned: cart.customer && ppp > 0 ? Math.floor(total / (ppp * 100)) : 0,
  }
}

export function useCart() {
  const [cart, setCart] = useState<CartState>(load)

  useEffect(() => {
    try {
      sessionStorage.setItem(KEY, JSON.stringify(cart))
    } catch {
      /* storage unavailable: cart just won't survive a reload */
    }
  }, [cart])

  const add = useCallback((p: PosProduct, mods: PosModifier[] = [], qty = 1, notes = '', size: PosSize | null = null) => {
    // A sized product added without choosing (e.g. a quick tap) takes its default size.
    const sz = size ?? p.sizes.find((s) => s.is_default) ?? p.sizes[0] ?? null
    const key = lineKey(p.id, sz?.size_id ?? null, mods, notes)
    setCart((c) => {
      const existing = c.lines.find((l) => l.key === key)
      if (existing) {
        return { ...c, lines: c.lines.map((l) => (l.key === key ? { ...l, qty: l.qty + qty } : l)) }
      }
      const line: CartLine = {
        key,
        product_id: p.id,
        category_id: p.category_id,
        name: p.name,
        size: sz ? { size_id: sz.size_id, name: sz.name, short_label: sz.short_label } : null,
        unit_cents: (sz ? sz.price_cents : p.price_cents) + mods.reduce((a, m) => a + m.price_delta_cents, 0),
        modifiers: mods,
        qty,
        notes: notes.trim(),
        discount_cents: 0,
      }
      return { ...c, lines: [...c.lines, line] }
    })
  }, [])

  /** A stamp-card reward: one free unit (its own $0 line). */
  const addReward = useCallback((p: PosProduct, size: PosSize | null, reward: { program_id: number; label: string }) => {
    setCart((c) => {
      if (c.lines.some((l) => l.reward?.program_id === reward.program_id)) return c
      const line: CartLine = {
        key: `reward|${reward.program_id}|${p.id}|${size?.size_id ?? ''}`,
        product_id: p.id,
        category_id: p.category_id,
        name: p.name,
        size: size ? { size_id: size.size_id, name: size.name, short_label: size.short_label } : null,
        unit_cents: size ? size.price_cents : p.price_cents,
        modifiers: [],
        qty: 1,
        notes: '',
        discount_cents: 0,
        reward,
      }
      return { ...c, lines: [...c.lines, line] }
    })
  }, [])
  const setReward = useCallback((reward: CartState['reward']) => setCart((c) => ({ ...c, reward })), [])

  const setQty = useCallback((key: string, qty: number) => {
    setCart((c) => {
      const line = c.lines.find((l) => l.key === key)
      if (!line || (line.reward && qty > 1)) return c // a reward is always one unit
      if (qty <= 0) return { ...c, lines: c.lines.filter((l) => l.key !== key) }
      return {
        ...c,
        lines: c.lines.map((l) => (l.key === key ? { ...l, qty, discount_cents: Math.min(l.discount_cents, l.unit_cents * qty) } : l)),
      }
    })
  }, [])

  const updateLine = useCallback((key: string, patch: Partial<Pick<CartLine, 'qty' | 'notes' | 'discount_cents'>>) => {
    setCart((c) => {
      const lines = c.lines.map((l) => {
        if (l.key !== key) return l
        const next = { ...l, ...patch }
        next.discount_cents = Math.min(Math.max(next.discount_cents, 0), next.unit_cents * next.qty)
        // Notes are part of the identity of a line.
        next.key = `${next.to_bar === false ? 'tab|' : ''}${lineKey(next.product_id, next.size?.size_id ?? null, next.modifiers, next.notes)}`
        return next
      })
      return { ...c, lines: lines.filter((l) => l.qty > 0) }
    })
  }, [])

  const remove = useCallback((key: string) => setCart((c) => ({ ...c, lines: c.lines.filter((l) => l.key !== key) })), [])
  const setChannel = useCallback((channel: Channel) => setCart((c) => ({ ...c, channel })), [])
  const setTable = useCallback((table_label: string) => setCart((c) => ({ ...c, table_label })), [])
  const setCustomer = useCallback(
    // Rewards belong to the customer's card: changing the customer drops them.
    (customer: PosCustomer | null) =>
      setCart((c) => ({ ...c, customer, points_to_redeem: 0, reward: null, lines: c.lines.filter((l) => !l.reward) })),
    [],
  )
  const setDiscount = useCallback((discount: CartState['discount']) => setCart((c) => ({ ...c, discount })), [])
  const setPoints = useCallback((points_to_redeem: number) => setCart((c) => ({ ...c, points_to_redeem })), [])
  const clear = useCallback(() => setCart(EMPTY), [])

  /** Replaces the cart with a table's open tab, priced with the current catalog. Returns lines it couldn't load. */
  const loadTab = useCallback((tab: Tab, products: PosProduct[]) => {
    const missing: string[] = []
    const lines: CartLine[] = []
    for (const ln of tab.lines) {
      const p = products.find((x) => x.id === ln.product_id)
      if (!p) {
        missing.push(ln.name)
        continue
      }
      const size = ln.size_id != null ? (p.sizes.find((s) => s.size_id === ln.size_id) ?? null) : null
      const mods = p.modifier_groups.flatMap((g) => g.modifiers).filter((m) => ln.modifier_ids.includes(m.id))
      lines.push({
        key: `tab|${lineKey(p.id, size?.size_id ?? null, mods, ln.notes ?? '')}`,
        product_id: p.id,
        category_id: p.category_id,
        name: p.name,
        size: size ? { size_id: size.size_id, name: size.name, short_label: size.short_label } : null,
        unit_cents: (size ? size.price_cents : p.price_cents) + mods.reduce((a, m) => a + m.price_delta_cents, 0),
        modifiers: mods,
        qty: ln.qty,
        notes: ln.notes ?? '',
        discount_cents: 0,
        to_bar: false,
      })
    }
    setCart({ ...EMPTY, lines, channel: 'salon', table_label: tab.table_label, tab: { id: tab.id, label: tab.table_label, prepaid_cents: tab.prepaid_cents ?? 0 } })
    return missing
  }, [])

  return useMemo(
    () => ({ cart, add, addReward, setReward, setQty, updateLine, remove, setChannel, setTable, setCustomer, setDiscount, setPoints, clear, loadTab }),
    [cart, add, addReward, setReward, setQty, updateLine, remove, setChannel, setTable, setCustomer, setDiscount, setPoints, clear, loadTab],
  )
}

export type CartApi = ReturnType<typeof useCart>
