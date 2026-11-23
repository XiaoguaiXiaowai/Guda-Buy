import http from '@/api/http'
import type { Paginated } from '@/types/catalog'
import type {
  AdminConversationQuery,
  AdminSupportConversation,
  ConversationCreatePayload,
  SupportConversation,
  SupportMessage,
  SupportMessageList,
} from '@/types/support'

export async function fetchMyConversations(params: { page?: number; page_size?: number } = {}) {
  const { data } = await http.get<Paginated<SupportConversation>>('/support/conversations/', {
    params,
  })
  return data
}

export async function createConversation(
  payload: ConversationCreatePayload = {},
): Promise<SupportConversation> {
  const { data } = await http.post<SupportConversation>('/support/conversations/', payload)
  return data
}

export async function fetchConversationMessages(
  publicId: string,
  after?: string,
): Promise<SupportMessageList> {
  const { data } = await http.get<SupportMessageList>(
    `/support/conversations/${publicId}/messages/`,
    { params: after ? { after } : {} },
  )
  return data
}

export async function sendConversationMessage(
  publicId: string,
  content: string,
): Promise<SupportMessage> {
  const { data } = await http.post<SupportMessage>(
    `/support/conversations/${publicId}/messages/`,
    { content },
  )
  return data
}

export async function fetchAdminConversations(
  query: AdminConversationQuery = {},
): Promise<Paginated<AdminSupportConversation>> {
  const { data } = await http.get<Paginated<AdminSupportConversation>>(
    '/admin/support/conversations/',
    { params: query },
  )
  return data
}

export async function assignConversation(
  publicId: string,
): Promise<AdminSupportConversation> {
  const { data } = await http.post<AdminSupportConversation>(
    `/admin/support/conversations/${publicId}/assign/`,
  )
  return data
}

export async function closeConversation(publicId: string): Promise<AdminSupportConversation> {
  const { data } = await http.post<AdminSupportConversation>(
    `/admin/support/conversations/${publicId}/close/`,
  )
  return data
}
