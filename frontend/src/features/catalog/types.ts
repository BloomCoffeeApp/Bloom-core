import type { Unit } from '../stock/types'

export interface ProductCategory {
  id: number
  name: string
  color: string
  icon: string
  sort_order: number
  active: boolean
  /** Its products go to the order screen (bar/kitchen). */
  send_to_orders: boolean
  product_count: number
}

export type CategoryInput = Omit<ProductCategory, 'id' | 'product_count'>

export interface RecipeLine {
  id: number | null
  stock_item_id: number
  stock_item_name: string
  unit: Unit
  qty: number
  unit_cost_cents: number
  line_cost_cents: number
}

export interface Size {
  id: number
  name: string
  short_label: string
  volume_ml: number | null
  sort_order: number
  active: boolean
  product_count: number
}

export type SizeInput = Omit<Size, 'id' | 'product_count'>

export interface SizeRecipeOverride {
  stock_item_id: number
  /** Replaces the scaled base qty of this stock item for the size (0 = not used). */
  qty: number
}

export interface ProductSize {
  size_id: number
  name: string
  short_label: string
  volume_ml: number | null
  active: boolean
  price_cents: number
  recipe_scale: number
  is_default: boolean
  recipe_overrides: SizeRecipeOverride[]
  /** Effective recipe of this size (base × scale + overrides). */
  recipe_items: RecipeLine[]
  cost_cents: number
  margin_pct: number | null
}

export interface ProductSizeInput {
  size_id: number
  price_cents: number
  recipe_scale: number
  is_default: boolean
  recipe_overrides: SizeRecipeOverride[]
}

/** Allergen/diet tags (fixed list, GET /product-tags). */
export interface ProductTag {
  code: string
  label: string
}

export interface Product {
  id: number
  name: string
  category_id: number | null
  category: { id: number; name: string; color: string; icon: string } | null
  description: string | null
  price_cents: number
  image_path: string | null
  image_url: string | null
  color: string | null
  active: boolean
  show_in_pos: boolean
  stock_item_id: number | null
  stock_item_name: string | null
  sort_order: number
  long_description: string | null
  tags: string[]
  featured: boolean
  /** Target prep minutes on the order screen (null = channel default; used with orders_pro). */
  prep_minutes: number | null
  cost_cents: number
  margin_pct: number | null
  recipe_items: RecipeLine[]
  modifier_group_ids: number[]
  sizes: ProductSize[]
  updated_at: string | null
}

export interface ProductInput {
  name: string
  category_id: number | null
  description: string | null
  price_cents: number
  color: string | null
  active: boolean
  show_in_pos: boolean
  stock_item_id: number | null
  sort_order: number
  long_description: string | null
  tags: string[]
  featured: boolean
  prep_minutes?: number | null
  recipe_items: { stock_item_id: number; qty: number }[]
  modifier_group_ids: number[]
  /** [] = no sizes (single price). */
  sizes: ProductSizeInput[]
}

export interface BulkPriceRow {
  product_id: number
  name: string
  size_id: number | null
  size_name: string | null
  category_id: number | null
  old_cents: number
  new_cents: number
}

export interface BulkPriceResult {
  applied: boolean
  count: number
  items: BulkPriceRow[]
}

export interface PriceHistoryEntry {
  id: number
  product_id: number
  old_cents: number
  new_cents: number
  size_id: number | null
  size_name: string | null
  change_pct: number | null
  user_id: number | null
  user_name: string | null
  ts: string
}

export interface ModifierRecipeLine {
  id?: number
  stock_item_id: number
  stock_item_name?: string
  unit?: Unit
  qty_delta: number
}

export interface Modifier {
  id: number
  name: string
  price_delta_cents: number
  sort_order: number
  recipe_items: ModifierRecipeLine[]
}

export interface ModifierGroup {
  id: number
  name: string
  min_select: number
  max_select: number
  modifiers: Modifier[]
  product_ids: number[]
}

export interface ModifierGroupInput {
  name: string
  min_select: number
  max_select: number
  modifiers: {
    id?: number | null
    name: string
    price_delta_cents: number
    sort_order: number
    recipe_items: { stock_item_id: number; qty_delta: number }[]
  }[]
}
