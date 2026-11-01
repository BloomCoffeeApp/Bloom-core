import { useCallback, useEffect, useMemo, useState } from 'react'

import type { PosConfig, CartLine, CartState, PosCustomer, PosModifier, PosProduct, PosSize } from './types'
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
  total: number
  items: number
  pointsEarned: number
}

/** Preview only: mirrors backend math (the backend always recalculates and validates). */
export function computeTotals(cart: CartState, cfg?: PosConfig): CartTotals {
  const subtotal = cart.lines.reduce((a, l) => a + l.unit_cents * l.qty - l.discount_cents, 0)
  const raw = cart.discount.mode === 'pct' ? Math.round((subtotal * cart.discount.value) / 100) : cart.discount.value
  const discount = Math.min(Math.max(raw, 0), subtotal)
  const ppr = cfg?.loyalty.points_per_reward ?? 0
  const rewardValue = cfg?.loyalty.reward_value_cents ?? 0
  const pointsDiscount =
    cart.points_to_redeem && ppr > 0
      ? Math.min(Math.floor(cart.points_to_redeem / ppr) * rewardValue, subtotal - discount)
      : 0
  const total = subtotal - discount - pointsDiscount
  const ppp = cfg?.loyalty.enabled ? cfg.loyalty.pesos_per_point : 0
  return {
    subtotal,
    discount,
    pointsDiscount,
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

  const setQty = useCallback((key: string, qty: number) => {
    setCart((c) => ({
      ...c,
      lines:
        qty <= 0
          ? c.lines.filter((l) => l.key !== key)
          : c.lines.map((l) =>
              l.key === key ? { ...l, qty, discount_cents: Math.min(l.discount_cents, l.unit_cents * qty) } : l,
            ),
    }))
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
    (customer: PosCustomer | null) => setCart((c) => ({ ...c, customer, points_to_redeem: 0 })),
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
    setCart({ ...EMPTY, lines, channel: 'salon', table_label: tab.table_label, tab: { id: tab.id, label: tab.table_label } })
    return missing
  }, [])

  return useMemo(
    () => ({ cart, add, setQty, updateLine, remove, setChannel, setTable, setCustomer, setDiscount, setPoints, clear, loadTab }),
    [cart, add, setQty, updateLine, remove, setChannel, setTable, setCustomer, setDiscount, setPoints, clear, loadTab],
  )
}

export type CartApi = ReturnType<typeof useCart>
