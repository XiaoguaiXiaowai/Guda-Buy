import type { SupportSenderRole, SupportStatus } from '@/types/support'

const STATUS_LABELS: Record<SupportStatus, string> = {
  WAITING: '待接入',
  ACTIVE: '进行中',
  CLOSED: '已关闭',
}

type TagTone = 'success' | 'warning' | 'info' | 'danger'

const STATUS_TONES: Record<SupportStatus, TagTone> = {
  WAITING: 'warning',
  ACTIVE: 'success',
  CLOSED: 'info',
}

const ROLE_LABELS: Record<SupportSenderRole, string> = {
  CUSTOMER: '我',
  AGENT: '客服',
  SYSTEM: '系统',
}

export function supportStatusLabel(status: SupportStatus, statusText?: string): string {
  return statusText?.trim() || STATUS_LABELS[status] || status
}

export function supportStatusTone(status: SupportStatus): TagTone {
  return STATUS_TONES[status] ?? 'info'
}

export function supportRoleLabel(role: SupportSenderRole, roleText?: string): string {
  return roleText?.trim() || ROLE_LABELS[role] || role
}
