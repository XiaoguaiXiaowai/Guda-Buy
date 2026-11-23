import http from '@/api/http'
import type { Paginated } from '@/types/catalog'
import type {
  OrderBrief,
  OrderCreatePayload,
  OrderDetail,
  OrderPreview,
  OrderPreviewPayload,
  OrderQuery,
  OrderSummary,
} from '@/types/order'

export async function fetchOrderPreview(payload: OrderPreviewPayload): Promise<OrderPreview> {
  const { data } = await http.post<OrderPreview>('/orders/preview/', payload)
  return data
}

export async function createOrder(
  payload: OrderCreatePayload,
  idempotencyKey: string,
): Promise<OrderDetail> {
  const { data } = await http.post<OrderDetail>('/orders/', payload, {
    headers: { 'Idempotency-Key': idempotencyKey },
  })
  return data
}

export async function fetchOrders(query: OrderQuery = {}): Promise<Paginated<OrderBrief>> {
  const { data } = await http.get<Paginated<OrderBrief>>('/orders/', { params: query })
  return data
}

export async function fetchOrderSummary(): Promise<OrderSummary> {
  const { data } = await http.get<OrderSummary>('/users/me/orders/summary/')
  return data
}

export async function fetchOrderDetail(orderNo: string): Promise<OrderDetail> {
  const { data } = await http.get<OrderDetail>(`/orders/${orderNo}/`)
  return data
}

export async function cancelOrder(orderNo: string): Promise<OrderDetail> {
  const { data } = await http.post<OrderDetail>(`/orders/${orderNo}/cancel/`)
  return data
}

export async function confirmOrder(orderNo: string): Promise<OrderDetail> {
  const { data } = await http.post<OrderDetail>(`/orders/${orderNo}/confirm/`)
  return data
}
