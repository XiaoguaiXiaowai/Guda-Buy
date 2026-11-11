import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'

import {
  getAccessToken,
  refreshAccessToken,
  setAccessToken,
} from '@/api/authToken'
import type { ApiError } from '@/types/api'

interface RetryConfig extends InternalAxiosRequestConfig {
  _retry?: boolean
}

const http = axios.create({
  baseURL: '/api/v1',
  timeout: 15000,
})

http.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = getAccessToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  // 配合后端 Cookie 刷新接口的 CSRF 兜底校验
  config.headers['X-Requested-With'] = 'XMLHttpRequest'
  return config
})

function shouldTryRefresh(url: string | undefined): boolean {
  return !url?.startsWith('/auth/')
}

http.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<ApiError>) => {
    const status = error.response?.status
    const config = error.config as RetryConfig | undefined

    if (status === 401 && config && !config._retry && shouldTryRefresh(config.url)) {
      config._retry = true
      const refreshed = await refreshAccessToken()
      if (refreshed) {
        const token = getAccessToken()
        if (token) {
          config.headers.Authorization = `Bearer ${token}`
        }
        return http(config)
      }
      setAccessToken(null)
    }

    const message =
      error.response?.data?.message ??
      (error.code === 'ECONNABORTED' ? '请求超时，请稍后重试' : '网络异常，请稍后重试')

    ElMessage.error(message)
    return Promise.reject(error)
  },
)

export default http
