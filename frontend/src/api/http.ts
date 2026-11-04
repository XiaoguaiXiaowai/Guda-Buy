import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'

import { useAuthStore } from '@/stores/auth'
import type { ApiError } from '@/types/api'

const http = axios.create({
  baseURL: '/api/v1',
  timeout: 15000,
})

http.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const auth = useAuthStore()
  if (auth.accessToken) {
    config.headers.Authorization = `Bearer ${auth.accessToken}`
  }
  // 配合后端 Cookie 刷新接口的 CSRF 兜底校验
  config.headers['X-Requested-With'] = 'XMLHttpRequest'
  return config
})

http.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiError>) => {
    const status = error.response?.status

    if (status === 401) {
      // I1 接入 refresh 轮换：此处预留「静默刷新并重放一次」的位置
      useAuthStore().clear()
    }

    const message =
      error.response?.data?.message ??
      (error.code === 'ECONNABORTED' ? '请求超时，请稍后重试' : '网络异常，请稍后重试')

    ElMessage.error(message)
    return Promise.reject(error)
  },
)

export default http
