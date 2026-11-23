import http from '@/api/http'
import type { Paginated } from '@/types/catalog'
import type {
  NotificationItem,
  NotificationQuery,
  NotificationReadResult,
  ReadAllResult,
  UnreadCount,
} from '@/types/notification'

export async function fetchNotifications(
  query: NotificationQuery = {},
): Promise<Paginated<NotificationItem>> {
  const { data } = await http.get<Paginated<NotificationItem>>('/notifications/', { params: query })
  return data
}

export async function fetchUnreadCount(): Promise<UnreadCount> {
  const { data } = await http.get<UnreadCount>('/notifications/unread-count/')
  return data
}

export async function markNotificationRead(publicId: string): Promise<NotificationReadResult> {
  const { data } = await http.post<NotificationReadResult>(`/notifications/${publicId}/read/`)
  return data
}

export async function markAllNotificationsRead(): Promise<ReadAllResult> {
  const { data } = await http.post<ReadAllResult>('/notifications/read-all/')
  return data
}
