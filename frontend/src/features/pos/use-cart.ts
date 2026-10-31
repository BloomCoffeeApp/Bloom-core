import { useCallback, useEffect, useMemo, useState } from 'react'

import type { PosConfig, CartLine, CartState, PosCustomer, PosModifier, PosProduct } from './types'
import type { Channel } from '../sales/types'

const KEY = 'pos.cart.v1'

const EMPTY: CartState = {
  lines: [],
  channel: 'salon',
  table_label: '',
  customer: null,
  discount: { mode: 'amount', value: 0 },
  points_to_redeem: 0,
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

const lineKey = (productId: number, mods: PosModifier[], notes: string) =>
  `${productId}|${mods.map((m) => m.id).sort((a, b) => a - b).join(',')}|${notes.trim().toLowerCase()}`

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

  const add = useCallback((p: PosProduct, mods: PosModifier[] = [], qty = 1, notes = '') => {
    const key = lineKey(p.id, mods, notes)
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
        unit_cents: p.price_cents + mods.reduce((a, m) => a + m.price_delta_cents, 0),
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
        next.key = lineKey(next.product_id, next.modifiers, next.notes)
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

  return useMemo(
    () => ({ cart, add, setQty, updateLine, remove, setChannel, setTable, setCustomer, setDiscount, setPoints, clear }),
    [cart, add, setQty, updateLine, remove, setChannel, setTable, setCustomer, setDiscount, setPoints, clear],
  )
}

export type CartApi = ReturnType<typeof useCart>
