import { describe, expect, it } from 'vitest'

import { supportRoleLabel, supportStatusLabel, supportStatusTone } from '@/utils/support'

describe('客服会话状态映射', () => {
  it('优先使用后端文案，缺失时回退本地映射', () => {
    expect(supportStatusLabel('WAITING')).toBe('待接入')
    expect(supportStatusLabel('ACTIVE', '进行中（人工）')).toBe('进行中（人工）')
    expect(supportStatusLabel('CLOSED')).toBe('已关闭')
  })

  it('不同状态对应不同标签色', () => {
    expect(supportStatusTone('WAITING')).toBe('warning')
    expect(supportStatusTone('ACTIVE')).toBe('success')
    expect(supportStatusTone('CLOSED')).toBe('info')
  })
})

describe('客服消息角色映射', () => {
  it('系统消息显示为系统，会员视角显示为我', () => {
    expect(supportRoleLabel('CUSTOMER')).toBe('我')
    expect(supportRoleLabel('AGENT', '客服小美')).toBe('客服小美')
    expect(supportRoleLabel('SYSTEM')).toBe('系统')
  })
})
