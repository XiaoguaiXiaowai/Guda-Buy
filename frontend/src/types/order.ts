export type OrderStatus =
  | 'PENDING_PAYMENT'
  | 'PAID'
  | 'SHIPPED'
  | 'COMPLETED'
  | 'CANCELLED'
  | 'REFUNDING'
  | 'REFUNDED'

export interface OrderItem {
  sku_public_id: string
  product_public_id: string
  product_name: string
  sku_spec: string
  main_image: string
  unit_price: string
  quantity: number
  item_amount: string
}

export interface OrderAddressSnapshot {
  address_public_id: string
  receiver_name: string
  phone: string
  province: string
  city: string
  district: string
  detail: string
  postal_code: string
}

export interface OrderPayment {
  payment_no: string
  channel: string
  channel_text: string
  status: string
  status_text: string
  amount: string
  paid_at: string | null
}

export interface OrderStatusLog {
  from_status: string
  from_status_text: string
  to_status: OrderStatus
  to_status_text: string
  remark: string
  created_at: string
}

export interface OrderBrief {
  order_no: string
  status: OrderStatus
  status_text: string
  items_amount: string
  payable_amount: string
  total_quantity: number
  items: OrderItem[]
  created_at: string
  pay_expires_at: string
  can_pay: boolean
  can_cancel: boolean
  can_confirm: boolean
}

export interface OrderDetail extends OrderBrief {
  discount_amount: string
  shipping_amount: string
  address: OrderAddressSnapshot
  remark: string
  tracking_no: string
  cancel_reason: string
  paid_at: string | null
  shipped_at: string | null
  completed_at: string | null
  cancelled_at: string | null
  payments: OrderPayment[]
  status_logs: OrderStatusLog[]
}

export interface OrderPreviewItem {
  cart_item_public_id: string
  sku_public_id: string
  product_public_id: string
  product_name: string
  sku_spec: string
  main_image: string
  unit_price: string
  quantity: number
  item_amount: string
}

export interface OrderPreview {
  address: OrderAddressSnapshot
  items: OrderPreviewItem[]
  items_amount: string
  discount_amount: string
  shipping_amount: string
  payable_amount: string
  free_shipping_threshold: string
}

export interface OrderPreviewPayload {
  cart_item_public_ids: string[]
  address_public_id: string
}

export interface OrderCreatePayload extends OrderPreviewPayload {
  remark?: string
}

export interface OrderQuery {
  status?: OrderStatus | ''
  order_no?: string
  page?: number
  page_size?: number
}

export interface OrderStatusOption {
  label: string
  value: OrderStatus | ''
}
