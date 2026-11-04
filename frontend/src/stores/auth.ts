import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

export const useAuthStore = defineStore('auth', () => {
  // access token 仅存内存，刷新页面后由 refresh Cookie 换取（I1 实现）
  const accessToken = ref<string | null>(null)

  const isAuthenticated = computed(() => accessToken.value !== null)

  function setAccessToken(token: string) {
    accessToken.value = token
  }

  function clear() {
    accessToken.value = null
  }

  return { accessToken, isAuthenticated, setAccessToken, clear }
})
