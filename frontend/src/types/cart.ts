export type CartItemStatus = 'VALID' | 'INVALID' | 'INSUFFICIENT'

export interface CartProductBrief {
  public_id: string
  name: string
  main_image: string
}

export interface CartItem {
  public_id: string
  sku_public_id: string
  sku_code: string
  spec_text: string
  specs: Record<string, string>
  product: CartProductBrief
  sale_price: string
  quantity: number
  is_selected: boolean
  subtotal: string
  stock: number
  status: CartItemStatus
  status_text: string
  status_reason: string
}

export interface CartSummary {
  items_count: number
  total_quantity: number
  selected_count: number
  valid_count: number
  items_amount: string
  can_checkout: boolean
}

export interface CartPayload {
  items: CartItem[]
  summary: CartSummary
}

export interface CartCount {
  count: number
  total_quantity: number
}

export interface AddCartItemPayload {
  sku_public_id: string
  quantity?: number
}

export interface UpdateCartItemPayload {
  quantity?: number
  is_selected?: boolean
}
