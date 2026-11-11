/**
 * access token 仅驻留内存，通过桥接对象供 Axios 读取，避免 http <-> store 循环依赖。
 */
let accessToken: string | null = null
let refreshHandler: (() => Promise<boolean>) | null = null

export function getAccessToken(): string | null {
  return accessToken
}

export function setAccessToken(token: string | null): void {
  accessToken = token
}

export function registerRefreshHandler(handler: () => Promise<boolean>): void {
  refreshHandler = handler
}

export async function refreshAccessToken(): Promise<boolean> {
  if (!refreshHandler) {
    return false
  }
  return refreshHandler()
}
