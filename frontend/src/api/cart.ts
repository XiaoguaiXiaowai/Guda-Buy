import http from '@/api/http'
import type {
  AddCartItemPayload,
  CartCount,
  CartItem,
  CartPayload,
  UpdateCartItemPayload,
} from '@/types/cart'

export async function fetchCart(): Promise<CartPayload> {
  const { data } = await http.get<CartPayload>('/cart/')
  return data
}

export async function addCartItem(payload: AddCartItemPayload): Promise<CartItem> {
  const { data } = await http.post<CartItem>('/cart/items/', {
    quantity: 1,
    ...payload,
  })
  return data
}

export async function updateCartItem(
  publicId: string,
  payload: UpdateCartItemPayload,
): Promise<CartItem | null> {
  const response = await http.patch<CartItem>(`/cart/items/${publicId}/`, payload)
  return response.status === 204 ? null : response.data
}

export async function deleteCartItem(publicId: string): Promise<void> {
  await http.delete(`/cart/items/${publicId}/`)
}

export async function clearCart(onlySelected = false): Promise<number> {
  const { data } = await http.post<{ deleted: number }>('/cart/clear/', {
    only_selected: onlySelected,
  })
  return data.deleted
}

export async function fetchCartCount(): Promise<CartCount> {
  const { data } = await http.get<CartCount>('/cart/count/')
  return data
}
