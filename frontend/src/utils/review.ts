import type { ReviewStatus } from '@/types/review'

const STATUS_LABELS: Record<ReviewStatus, string> = {
  PENDING: '待审核',
  APPROVED: '已通过',
  REJECTED: '已驳回',
}

const STATUS_TONES: Record<ReviewStatus, 'warning' | 'success' | 'danger'> = {
  PENDING: 'warning',
  APPROVED: 'success',
  REJECTED: 'danger',
}

export function reviewStatusLabel(status: ReviewStatus, fallback?: string): string {
  return fallback || STATUS_LABELS[status] || status
}

export function reviewStatusTone(status: ReviewStatus): 'warning' | 'success' | 'danger' {
  return STATUS_TONES[status] ?? 'warning'
}

/** 星级分布百分比：用于商品详情的评分条。 */
export function distributionPercent(count: number, total: number): number {
  if (!total) {
    return 0
  }
  return Math.round((count / total) * 100)
}

/** 最多 3 张：剩余可上传张数。 */
export function remainingImageSlots(existing: number, limit = 3): number {
  return Math.max(limit - existing, 0)
}
