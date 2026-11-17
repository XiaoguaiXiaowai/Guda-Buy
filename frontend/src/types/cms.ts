import type { ProductListItem } from '@/types/catalog'

export type CmsSectionStatus = 'ENABLED' | 'DISABLED'
export type CmsPageStatus = 'DRAFT' | 'PUBLISHED' | 'OFFLINE'
export type CmsBannerPosition = 'HOME_TOP' | 'HOME_MIDDLE'
export type CmsBannerStatus = 'ENABLED' | 'DISABLED'
export type CmsAnnouncementLevel = 'NORMAL' | 'IMPORTANT'
export type CmsAnnouncementStatus = 'ENABLED' | 'DISABLED'

export interface CmsSectionBrief {
  public_id: string
  name: string
  slug: string
}

export interface CmsPage {
  public_id: string
  slug: string
  title: string
  content: string
  seo_title: string
  seo_description: string
  section: CmsSectionBrief
  published_at: string | null
  updated_at: string
}

export interface CmsBanner {
  public_id: string
  position: CmsBannerPosition
  title: string
  image: string
  link_url: string
  sort_weight: number
}

export interface CmsAnnouncement {
  public_id: string
  title: string
  content: string
  level: CmsAnnouncementLevel
  published_at: string | null
}

export interface CmsHome {
  banners: CmsBanner[]
  announcements: CmsAnnouncement[]
  recommended_products: ProductListItem[]
  generated_at: string
}

// ---------------------------------------------------------------------------
// 后台
// ---------------------------------------------------------------------------
export interface AdminCmsSection {
  public_id: string
  name: string
  slug: string
  sort_weight: number
  status: CmsSectionStatus
  page_count: number
  created_at: string
  updated_at: string
}

export interface AdminCmsSectionPayload {
  name?: string
  slug?: string
  sort_weight?: number
  status?: CmsSectionStatus
}

export interface AdminCmsPage {
  public_id: string
  slug: string
  title: string
  content: string
  status: CmsPageStatus
  published_at: string | null
  seo_title: string
  seo_description: string
  sort_weight: number
  section: AdminCmsSection
  created_at: string
  updated_at: string
}

export interface AdminCmsPagePayload {
  section_public_id?: string
  slug?: string
  title?: string
  content?: string
  seo_title?: string
  seo_description?: string
  sort_weight?: number
}

export interface AdminCmsBanner {
  public_id: string
  position: CmsBannerPosition
  title: string
  image: string
  link_url: string
  sort_weight: number
  status: CmsBannerStatus
  start_at: string | null
  end_at: string | null
  created_at: string
  updated_at: string
}

export interface AdminCmsBannerPayload {
  position?: CmsBannerPosition
  title?: string
  image?: string
  link_url?: string
  sort_weight?: number
  status?: CmsBannerStatus
  start_at?: string | null
  end_at?: string | null
}

export interface AdminCmsAnnouncement {
  public_id: string
  title: string
  content: string
  level: CmsAnnouncementLevel
  status: CmsAnnouncementStatus
  published_at: string | null
  created_at: string
  updated_at: string
}

export interface AdminCmsAnnouncementPayload {
  title?: string
  content?: string
  level?: CmsAnnouncementLevel
  status?: CmsAnnouncementStatus
}

export interface CmsPageQuery {
  status?: string
  section?: string
  search?: string
  page?: number
  page_size?: number
}
