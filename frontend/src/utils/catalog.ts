import type { ProductStatus, StockStatus } from '@/types/catalog'
import { formatCurrency } from '@/utils/format'

/** 后端返回相对媒体路径，统一补齐 /media 前缀；绝对地址原样返回。 */
export function resolveImageUrl(path?: string | null): string {
  if (!path) {
    return ''
  }
  if (/^https?:\/\//.test(path) || path.startsWith('/')) {
    return path
  }
  return `/media/${path.replace(/^\/+/, '')}`
}

/** 同价展示单价，不同价展示「¥min 起」。 */
export function formatPriceRange(min: string, max: string): string {
  const low = Number(min)
  const high = Number(max)
  if (!Number.isFinite(low) || low <= 0) {
    return '待定价'
  }
  if (!Number.isFinite(high) || high <= low) {
    return formatCurrency(low)
  }
  return `${formatCurrency(low)} 起`
}

export function stockTone(status: StockStatus): 'success' | 'warning' | 'danger' {
  if (status === 'OUT_OF_STOCK') {
    return 'danger'
  }
  return status === 'LOW' ? 'warning' : 'success'
}

const PRODUCT_STATUS_LABELS: Record<ProductStatus, string> = {
  DRAFT: '草稿',
  ON_SALE: '在售',
  OFF_SALE: '已下架',
}

export function productStatusLabel(status: ProductStatus): string {
  return PRODUCT_STATUS_LABELS[status] ?? status
}

export function productStatusTone(status: ProductStatus): 'info' | 'success' | 'warning' {
  if (status === 'ON_SALE') {
    return 'success'
  }
  return status === 'DRAFT' ? 'info' : 'warning'
}

/** 去掉空值，避免把空字符串传给后端导致校验失败。 */
export function toQueryParams(
  query: Record<string, string | number | undefined>,
): Record<string, string | number> {
  return Object.fromEntries(
    Object.entries(query).filter(([, value]) => value !== undefined && value !== ''),
  ) as Record<string, string | number>
}
