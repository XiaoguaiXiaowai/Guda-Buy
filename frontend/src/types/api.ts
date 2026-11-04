export interface ApiError {
  code: string
  message: string
  detail: Record<string, unknown> | null
  request_id: string
  timestamp: string
}
