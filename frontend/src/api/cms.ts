import http from '@/api/http'
import type {
  AdminCmsAnnouncement,
  AdminCmsAnnouncementPayload,
  AdminCmsBanner,
  AdminCmsBannerPayload,
  AdminCmsPage,
  AdminCmsPagePayload,
  AdminCmsSection,
  AdminCmsSectionPayload,
  CmsBanner,
  CmsHome,
  CmsPage,
  CmsPageQuery,
} from '@/types/cms'
import type { Paginated } from '@/types/catalog'

// ---------------------------------------------------------------------------
// 前台
// ---------------------------------------------------------------------------
export async function fetchCmsPage(slug: string): Promise<CmsPage> {
  const { data } = await http.get<CmsPage>(`/cms/pages/${slug}/`)
  return data
}

export async function fetchCmsBanners(params: { position?: string } = {}): Promise<CmsBanner[]> {
  const { data } = await http.get<CmsBanner[]>('/cms/banners/', { params })
  return data
}

export async function fetchCmsHome(): Promise<CmsHome> {
  const { data } = await http.get<CmsHome>('/cms/home/')
  return data
}

// ---------------------------------------------------------------------------
// 后台：栏目
// ---------------------------------------------------------------------------
export async function fetchAdminCmsSections(): Promise<AdminCmsSection[]> {
  const { data } = await http.get<AdminCmsSection[]>('/admin/cms/sections/')
  return data
}

export async function createCmsSection(payload: AdminCmsSectionPayload): Promise<AdminCmsSection> {
  const { data } = await http.post<AdminCmsSection>('/admin/cms/sections/', payload)
  return data
}

export async function updateCmsSection(
  publicId: string,
  payload: AdminCmsSectionPayload,
): Promise<AdminCmsSection> {
  const { data } = await http.put<AdminCmsSection>(`/admin/cms/sections/${publicId}/`, payload)
  return data
}

export async function deleteCmsSection(publicId: string): Promise<void> {
  await http.delete(`/admin/cms/sections/${publicId}/`)
}

// ---------------------------------------------------------------------------
// 后台：页面
// ---------------------------------------------------------------------------
export async function fetchAdminCmsPages(
  params: CmsPageQuery = {},
): Promise<Paginated<AdminCmsPage>> {
  const { data } = await http.get<Paginated<AdminCmsPage>>('/admin/cms/pages/', { params })
  return data
}

export async function createCmsPage(payload: AdminCmsPagePayload): Promise<AdminCmsPage> {
  const { data } = await http.post<AdminCmsPage>('/admin/cms/pages/', payload)
  return data
}

export async function updateCmsPage(
  publicId: string,
  payload: AdminCmsPagePayload,
): Promise<AdminCmsPage> {
  const { data } = await http.put<AdminCmsPage>(`/admin/cms/pages/${publicId}/`, payload)
  return data
}

export async function changeCmsPageStatus(
  publicId: string,
  action: 'PUBLISH' | 'OFFLINE',
): Promise<AdminCmsPage> {
  const { data } = await http.post<AdminCmsPage>(`/admin/cms/pages/${publicId}/publish/`, {
    action,
  })
  return data
}

export async function deleteCmsPage(publicId: string): Promise<void> {
  await http.delete(`/admin/cms/pages/${publicId}/`)
}

// ---------------------------------------------------------------------------
// 后台：轮播
// ---------------------------------------------------------------------------
export async function fetchAdminCmsBanners(
  params: { position?: string; status?: string } = {},
): Promise<AdminCmsBanner[]> {
  const { data } = await http.get<AdminCmsBanner[]>('/admin/cms/banners/', { params })
  return data
}

export async function createCmsBanner(payload: AdminCmsBannerPayload): Promise<AdminCmsBanner> {
  const { data } = await http.post<AdminCmsBanner>('/admin/cms/banners/', payload)
  return data
}

export async function updateCmsBanner(
  publicId: string,
  payload: AdminCmsBannerPayload,
): Promise<AdminCmsBanner> {
  const { data } = await http.put<AdminCmsBanner>(`/admin/cms/banners/${publicId}/`, payload)
  return data
}

export async function uploadCmsBannerImage(publicId: string, file: File): Promise<AdminCmsBanner> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await http.post<AdminCmsBanner>(`/admin/cms/banners/${publicId}/image/`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function deleteCmsBanner(publicId: string): Promise<void> {
  await http.delete(`/admin/cms/banners/${publicId}/`)
}

// ---------------------------------------------------------------------------
// 后台：公告
// ---------------------------------------------------------------------------
export async function fetchAdminCmsAnnouncements(
  params: { status?: string; level?: string } = {},
): Promise<AdminCmsAnnouncement[]> {
  const { data } = await http.get<AdminCmsAnnouncement[]>('/admin/cms/announcements/', {
    params,
  })
  return data
}

export async function createCmsAnnouncement(
  payload: AdminCmsAnnouncementPayload,
): Promise<AdminCmsAnnouncement> {
  const { data } = await http.post<AdminCmsAnnouncement>('/admin/cms/announcements/', payload)
  return data
}

export async function updateCmsAnnouncement(
  publicId: string,
  payload: AdminCmsAnnouncementPayload,
): Promise<AdminCmsAnnouncement> {
  const { data } = await http.put<AdminCmsAnnouncement>(
    `/admin/cms/announcements/${publicId}/`,
    payload,
  )
  return data
}

export async function deleteCmsAnnouncement(publicId: string): Promise<void> {
  await http.delete(`/admin/cms/announcements/${publicId}/`)
}
