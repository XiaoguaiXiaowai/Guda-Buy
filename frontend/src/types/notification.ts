export type NotificationType =
  | 'ORDER_PAID'
  | 'ORDER_SHIPPED'
  | 'ORDER_CANCELLED'
  | 'COUPON_EXPIRING'
  | 'SYSTEM'

export interface NotificationItem {
  public_id: string
  type: NotificationType
  type_text: string
  title: string
  content: string
  biz_type: string
  biz_public_id: string
  is_read: boolean
  read_at: string | null
  created_at: string
}

export interface NotificationQuery {
  type?: NotificationType | ''
  page?: number
  page_size?: number
}

export interface NotificationReadResult {
  public_id: string
  is_read: boolean
  read_at: string | null
  unread_count: number
}

export interface ReadAllResult {
  updated: number
  unread_count: number
}

export interface UnreadCount {
  unread_count: number
}

export interface NotificationTypeOption {
  label: string
  value: NotificationType | ''
}
