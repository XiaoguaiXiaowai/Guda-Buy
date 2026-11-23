export type SupportStatus = 'WAITING' | 'ACTIVE' | 'CLOSED'
export type SupportSenderRole = 'CUSTOMER' | 'AGENT' | 'SYSTEM'

export interface SupportOrderSummary {
  order_no: string
  status: string
  status_text: string
  payable_amount: string
  created_at: string
}

export interface SupportConversation {
  public_id: string
  status: SupportStatus
  status_text: string
  agent_name: string
  order: SupportOrderSummary | null
  last_message_at: string
  closed_at: string | null
  created_at: string
}

export interface SupportUserSummary {
  public_id: string
  nickname: string
  username: string
  created_at: string
  last_login_at: string | null
}

export interface AdminSupportConversation extends SupportConversation {
  user: SupportUserSummary
  agent_public_id: string
}

export interface SupportMessage {
  public_id: string
  sender_role: SupportSenderRole
  sender_role_text: string
  sender_name: string
  content: string
  is_read: boolean
  created_at: string
}

export interface SupportMessageList {
  conversation: SupportConversation | AdminSupportConversation
  messages: SupportMessage[]
  next_after: string
}

export interface ConversationCreatePayload {
  order_no?: string
}

export interface AdminConversationQuery {
  status?: SupportStatus | 'ALL' | ''
  keyword?: string
  page?: number
  page_size?: number
}
