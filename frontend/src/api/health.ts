import http from '@/api/http'

export interface HealthStatus {
  status: string
  db: string
  redis: string
}

/** 健康检查不在 /api/v1 下，单独覆盖 baseURL。 */
export async function fetchHealth(): Promise<HealthStatus> {
  const { data } = await http.get<HealthStatus>('/healthz/', { baseURL: '' })
  return data
}
