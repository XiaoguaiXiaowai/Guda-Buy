export type ProductStatus = 'DRAFT' | 'ON_SALE' | 'OFF_SALE'
export type SkuStatus = 'ON_SALE' | 'OFF_SALE'
export type StockStatus = 'IN_STOCK' | 'LOW' | 'OUT_OF_STOCK'

export interface CategoryNode {
  public_id: string
  name: string
  sort_weight: number
  product_count: number
  children: CategoryNode[]
}

export interface ProductCategoryBrief {
  public_id: string
  name: string
}

export interface ProductListItem {
  public_id: string
  name: string
  subtitle: string
  main_image: string
  price_min: string
  price_max: string
  sales_count: number
  category: ProductCategoryBrief
}

export interface ProductSuggestion {
  public_id: string
  name: string
  price_min: string
  main_image: string
}

export interface ProductImage {
  public_id: string
  image: string
  sort_order: number
}

export interface Sku {
  public_id: string
  sku_code: string
  spec_text: string
  specs: Record<string, string>
  sale_price: string
  original_price: string | null
  stock: number
  stock_status: StockStatus
  stock_text: string
  status: SkuStatus
}

export interface ReviewSummary {
  average: string
  count: number
  distribution: Record<string, number>
}

export interface ProductDetail extends ProductListItem {
  description: string
  images: ProductImage[]
  skus: Sku[]
  review_summary: ReviewSummary
  created_at: string
}

export interface Paginated<T> {
  count: number
  page: number
  page_size: number
  total_pages: number
  next: string | null
  previous: string | null
  results: T[]
}

export interface ProductQuery {
  category?: string
  price_min?: string
  price_max?: string
  search?: string
  ordering?: string
  page?: number
  page_size?: number
}

export interface AdminCategory {
  public_id: string
  name: string
  parent_public_id: string | null
  level: number
  sort_weight: number
  product_count: number
}

export interface AdminCategoryPayload {
  name: string
  parent_public_id?: string
  sort_weight?: number
}

export interface AdminProduct {
  public_id: string
  name: string
  subtitle: string
  description: string
  main_image: string
  price_min: string
  price_max: string
  sales_count: number
  status: ProductStatus
  sort_weight: number
  category: AdminCategory
  images: ProductImage[]
  sku_count: number
  stock_total: number
  created_at: string
  updated_at: string
}

export interface AdminProductPayload {
  category_public_id?: string
  name?: string
  subtitle?: string
  description?: string
  main_image?: string
  sort_weight?: number
}

export interface AdminSku {
  public_id: string
  sku_code: string
  spec_text: string
  specs: Record<string, string>
  sale_price: string
  original_price: string | null
  stock: number
  locked_stock: number
  stock_capacity: number
  status: SkuStatus
  weight_grams: number
  stock_status: StockStatus
  stock_text: string
  created_at: string
  updated_at: string
}

export interface AdminSkuPayload {
  sku_code?: string
  spec_text?: string
  specs?: Record<string, string>
  sale_price?: string
  original_price?: string | null
  stock?: number
  stock_capacity?: number
  weight_grams?: number
  status?: SkuStatus
}
