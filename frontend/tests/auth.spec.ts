import axios from 'axios'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { getAccessToken, setAccessToken } from '@/api/authToken'
import * as userApi from '@/api/user'
import { useAuthStore } from '@/stores/auth'
import type { AuthResponse, UserProfile } from '@/types/user'

vi.mock('axios', () => ({
  default: { post: vi.fn() },
}))

vi.mock('@/api/user', () => ({
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
  fetchMe: vi.fn(),
}))

const profile: UserProfile = {
  public_id: 'abc123',
  username: 'guda_user',
  email: 'guda@example.com',
  nickname: '古达',
  gender: 'UNKNOWN',
  gender_label: '保密',
  birthday: null,
  avatar: null,
  created_at: '2026-11-11T10:00:00+08:00',
}

const session: AuthResponse = {
  access: 'access-token',
  expires_in: 1800,
  user: profile,
}

describe('auth store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    setAccessToken(null)
    vi.clearAllMocks()
  })

  it('登录后仅把 access 放在内存，localStorage 只留会话提示', async () => {
    vi.mocked(userApi.login).mockResolvedValue(session)
    const auth = useAuthStore()

    await auth.login({ account: 'guda_user', password: 'Passw0rd123' })

    expect(auth.isAuthenticated).toBe(true)
    expect(auth.user?.nickname).toBe('古达')
    expect(getAccessToken()).toBe('access-token')
    expect(localStorage.getItem('guda.session')).toBe('1')
    expect(JSON.stringify(localStorage)).not.toContain('access-token')
  })

  it('刷新页面后用 refresh Cookie 恢复会话', async () => {
    localStorage.setItem('guda.session', '1')
    vi.mocked(axios.post).mockResolvedValue({ data: { access: 'restored-access' } })
    vi.mocked(userApi.fetchMe).mockResolvedValue(profile)
    const auth = useAuthStore()

    const ready = await auth.ensureSession()

    expect(ready).toBe(true)
    expect(getAccessToken()).toBe('restored-access')
    expect(auth.user?.email).toBe('guda@example.com')
    expect(axios.post).toHaveBeenCalledWith(
      '/api/v1/auth/refresh/',
      {},
      expect.objectContaining({ headers: { 'X-Requested-With': 'XMLHttpRequest' } }),
    )
  })

  it('refresh 失效时清除本地登录态且不保留会话提示', async () => {
    localStorage.setItem('guda.session', '1')
    vi.mocked(axios.post).mockRejectedValue(new Error('401'))
    const auth = useAuthStore()

    const ready = await auth.ensureSession()

    expect(ready).toBe(false)
    expect(auth.isAuthenticated).toBe(false)
    expect(getAccessToken()).toBeNull()
    expect(localStorage.getItem('guda.session')).toBeNull()
  })

  it('登出时清空用户与令牌', async () => {
    vi.mocked(userApi.login).mockResolvedValue(session)
    vi.mocked(userApi.logout).mockResolvedValue()
    const auth = useAuthStore()
    await auth.login({ account: 'guda_user', password: 'Passw0rd123' })

    await auth.logout()

    expect(auth.isAuthenticated).toBe(false)
    expect(getAccessToken()).toBeNull()
    expect(localStorage.getItem('guda.session')).toBeNull()
  })

  it('无会话提示时不发起 refresh 请求', async () => {
    const auth = useAuthStore()

    const ready = await auth.ensureSession()

    expect(ready).toBe(false)
    expect(axios.post).not.toHaveBeenCalled()
  })
})
