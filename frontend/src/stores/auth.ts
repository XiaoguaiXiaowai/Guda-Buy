import axios from 'axios'
import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { registerRefreshHandler, setAccessToken } from '@/api/authToken'
import {
  fetchMe,
  login as loginApi,
  logout as logoutApi,
  register as registerApi,
} from '@/api/user'
import type { AuthResponse, LoginPayload, RegisterPayload, UserProfile } from '@/types/user'

const SESSION_HINT_KEY = 'guda.session'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<UserProfile | null>(null)
  const isAuthenticated = computed(() => user.value !== null)
  let refreshPromise: Promise<boolean> | null = null

  function applySession(payload: AuthResponse) {
    setAccessToken(payload.access)
    user.value = payload.user
    localStorage.setItem(SESSION_HINT_KEY, '1')
  }

  function clear() {
    setAccessToken(null)
    user.value = null
    localStorage.removeItem(SESSION_HINT_KEY)
  }

  async function refreshSession(): Promise<boolean> {
    if (refreshPromise) {
      return refreshPromise
    }
    refreshPromise = (async () => {
      try {
        const { data } = await axios.post<{ access: string }>(
          '/api/v1/auth/refresh/',
          {},
          {
            timeout: 15000,
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
          },
        )
        setAccessToken(data.access)
        return true
      } catch {
        clear()
        return false
      } finally {
        refreshPromise = null
      }
    })()
    return refreshPromise
  }

  async function loadProfile(): Promise<void> {
    user.value = await fetchMe()
  }

  /** 路由守卫使用：优先内存 token，其次用 refresh Cookie 恢复会话。 */
  async function ensureSession(): Promise<boolean> {
    if (user.value) {
      return true
    }
    if (!localStorage.getItem(SESSION_HINT_KEY)) {
      return false
    }
    const refreshed = await refreshSession()
    if (!refreshed) {
      return false
    }
    try {
      await loadProfile()
      return true
    } catch {
      clear()
      return false
    }
  }

  async function login(payload: LoginPayload): Promise<void> {
    applySession(await loginApi(payload))
  }

  /** 应用启动时静默恢复会话，用于公共页面展示登录态。 */
  async function restoreOnBoot(): Promise<void> {
    if (localStorage.getItem(SESSION_HINT_KEY)) {
      await ensureSession()
    }
  }

  function setProfile(profile: UserProfile): void {
    user.value = profile
  }

  async function register(payload: RegisterPayload): Promise<void> {
    applySession(await registerApi(payload))
  }

  async function logout(): Promise<void> {
    try {
      await logoutApi()
    } catch {
      // 令牌已失效也视为登出成功
    } finally {
      clear()
    }
  }

  registerRefreshHandler(refreshSession)

  return {
    user,
    isAuthenticated,
    ensureSession,
    restoreOnBoot,
    setProfile,
    loadProfile,
    login,
    register,
    logout,
    clear,
  }
})
