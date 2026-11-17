import type {
  CmsAnnouncementLevel,
  CmsBannerPosition,
  CmsPageStatus,
  CmsSectionStatus,
} from '@/types/cms'

const PAGE_STATUS_LABELS: Record<CmsPageStatus, string> = {
  DRAFT: '草稿',
  PUBLISHED: '已发布',
  OFFLINE: '已下线',
}

const SECTION_STATUS_LABELS: Record<CmsSectionStatus, string> = {
  ENABLED: '启用',
  DISABLED: '停用',
}

const POSITION_LABELS: Record<CmsBannerPosition, string> = {
  HOME_TOP: '首页顶部',
  HOME_MIDDLE: '首页中部',
}

const LEVEL_LABELS: Record<CmsAnnouncementLevel, string> = {
  NORMAL: '普通',
  IMPORTANT: '重要',
}

export function cmsPageStatusLabel(status: CmsPageStatus): string {
  return PAGE_STATUS_LABELS[status] ?? status
}

export function cmsPageStatusTone(status: CmsPageStatus): 'info' | 'success' | 'warning' {
  if (status === 'PUBLISHED') {
    return 'success'
  }
  return status === 'DRAFT' ? 'info' : 'warning'
}

export function sectionStatusLabel(status: CmsSectionStatus): string {
  return SECTION_STATUS_LABELS[status] ?? status
}

export function bannerPositionLabel(position: CmsBannerPosition): string {
  return POSITION_LABELS[position] ?? position
}

export function announcementLevelLabel(level: CmsAnnouncementLevel): string {
  return LEVEL_LABELS[level] ?? level
}

export function announcementLevelTone(level: CmsAnnouncementLevel): 'info' | 'danger' {
  return level === 'IMPORTANT' ? 'danger' : 'info'
}

export interface BannerWindow {
  start_at: string | null
  end_at: string | null
}

export type BannerWindowState = 'ALWAYS' | 'SCHEDULED' | 'ACTIVE' | 'EXPIRED'

/** 展示窗口状态：未开始 / 展示中 / 已结束 / 长期展示。 */
export function bannerWindowState(banner: BannerWindow, now: Date = new Date()): BannerWindowState {
  const start = banner.start_at ? new Date(banner.start_at) : null
  const end = banner.end_at ? new Date(banner.end_at) : null
  if (!start && !end) {
    return 'ALWAYS'
  }
  if (start && now < start) {
    return 'SCHEDULED'
  }
  if (end && now > end) {
    return 'EXPIRED'
  }
  return 'ACTIVE'
}

export function bannerWindowLabel(state: BannerWindowState): string {
  if (state === 'SCHEDULED') {
    return '未开始'
  }
  if (state === 'EXPIRED') {
    return '已结束'
  }
  return state === 'ALWAYS' ? '长期展示' : '展示中'
}

export function bannerWindowTone(state: BannerWindowState): 'info' | 'success' | 'warning' {
  if (state === 'ACTIVE') {
    return 'success'
  }
  return state === 'SCHEDULED' ? 'info' : 'warning'
}

export const CMS_SLUG_PATTERN = /^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$/

export function isValidCmsSlug(value: string): boolean {
  return CMS_SLUG_PATTERN.test(value.trim().toLowerCase())
}
