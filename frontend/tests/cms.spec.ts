import { describe, expect, it } from 'vitest'

import {
  announcementLevelLabel,
  announcementLevelTone,
  bannerPositionLabel,
  bannerWindowLabel,
  bannerWindowState,
  bannerWindowTone,
  cmsPageStatusLabel,
  cmsPageStatusTone,
  isValidCmsSlug,
  sectionStatusLabel,
} from '@/utils/cms'

describe('cmsPageStatusLabel / tone', () => {
  it('映射页面状态中文与标签色', () => {
    expect(cmsPageStatusLabel('DRAFT')).toBe('草稿')
    expect(cmsPageStatusLabel('PUBLISHED')).toBe('已发布')
    expect(cmsPageStatusLabel('OFFLINE')).toBe('已下线')
    expect(cmsPageStatusTone('PUBLISHED')).toBe('success')
    expect(cmsPageStatusTone('DRAFT')).toBe('info')
    expect(cmsPageStatusTone('OFFLINE')).toBe('warning')
  })
})

describe('sectionStatusLabel / position / level', () => {
  it('映射栏目、位置与公告级别', () => {
    expect(sectionStatusLabel('ENABLED')).toBe('启用')
    expect(sectionStatusLabel('DISABLED')).toBe('停用')
    expect(bannerPositionLabel('HOME_TOP')).toBe('首页顶部')
    expect(bannerPositionLabel('HOME_MIDDLE')).toBe('首页中部')
    expect(announcementLevelLabel('IMPORTANT')).toBe('重要')
    expect(announcementLevelTone('IMPORTANT')).toBe('danger')
    expect(announcementLevelTone('NORMAL')).toBe('info')
  })
})

describe('bannerWindowState', () => {
  const now = new Date('2026-11-17T12:00:00+08:00')

  it('无起止时间为长期展示', () => {
    expect(bannerWindowState({ start_at: null, end_at: null }, now)).toBe('ALWAYS')
  })

  it('未到开始时间为未开始', () => {
    expect(bannerWindowState({ start_at: '2026-11-18T00:00:00+08:00', end_at: null }, now)).toBe(
      'SCHEDULED',
    )
  })

  it('处于窗口内为展示中', () => {
    expect(
      bannerWindowState(
        { start_at: '2026-11-16T00:00:00+08:00', end_at: '2026-11-18T00:00:00+08:00' },
        now,
      ),
    ).toBe('ACTIVE')
  })

  it('超过结束时间为已结束', () => {
    expect(
      bannerWindowState(
        { start_at: '2026-11-10T00:00:00+08:00', end_at: '2026-11-16T00:00:00+08:00' },
        now,
      ),
    ).toBe('EXPIRED')
  })

  it('窗口文案与标签色保持一致', () => {
    expect(bannerWindowLabel('SCHEDULED')).toBe('未开始')
    expect(bannerWindowLabel('ACTIVE')).toBe('展示中')
    expect(bannerWindowLabel('EXPIRED')).toBe('已结束')
    expect(bannerWindowLabel('ALWAYS')).toBe('长期展示')
    expect(bannerWindowTone('ACTIVE')).toBe('success')
    expect(bannerWindowTone('SCHEDULED')).toBe('info')
    expect(bannerWindowTone('EXPIRED')).toBe('warning')
  })
})

describe('isValidCmsSlug', () => {
  it('接受小写字母、数字与中划线', () => {
    expect(isValidCmsSlug('help-center')).toBe(true)
    expect(isValidCmsSlug('promo2026')).toBe(true)
    expect(isValidCmsSlug('a')).toBe(true)
  })

  it('拒绝中文、空格与首尾中划线', () => {
    expect(isValidCmsSlug('帮助中心')).toBe(false)
    expect(isValidCmsSlug('bad slug')).toBe(false)
    expect(isValidCmsSlug('-leading')).toBe(false)
    expect(isValidCmsSlug('trailing-')).toBe(false)
  })

  it('大写会被归一化后接受', () => {
    expect(isValidCmsSlug('Help-Center')).toBe(true)
  })
})
