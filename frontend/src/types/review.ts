export type ReviewStatus = 'PENDING' | 'APPROVED' | 'REJECTED'

export interface ReviewImage {
  public_id: string
  image: string
  sort_order: number
}

export interface PublicReview {
  public_id: string
  rating: number
  content: string
  is_anonymous: boolean
  display_name: string
  avatar: string
  sku_spec: string
  images: ReviewImage[]
  created_at: string
}

export interface OrderReview {
  public_id: string
  order_no: string
  product_public_id: string
  product_name: string
  sku_public_id: string
  sku_spec: string
  rating: number
  content: string
  status: ReviewStatus
  status_text: string
  reject_reason: string
  is_anonymous: boolean
  images: ReviewImage[]
  created_at: string
  updated_at: string
}

export interface ReviewEligibility {
  order_no: string
  can_review: boolean
  reason: string
  requires_sku: boolean
  items: ReviewOrderItem[]
  review: OrderReview | null
  window_expires_at: string | null
}

export interface ReviewOrderItem {
  sku_public_id: string
  product_name: string
  sku_spec: string
}

export interface ReviewSubmitPayload {
  rating: number
  content: string
  is_anonymous: boolean
  sku_public_id?: string
}

export interface AdminReview {
  public_id: string
  order_no: string
  user: {
    public_id: string
    nickname: string
    username: string
  }
  product: {
    public_id: string
    name: string
  }
  sku_spec: string
  rating: number
  content: string
  status: ReviewStatus
  status_text: string
  reject_reason: string
  is_anonymous: boolean
  images: ReviewImage[]
  created_at: string
  updated_at: string
}

export interface AdminReviewQuery {
  status?: ReviewStatus | ''
  rating?: number | ''
  keyword?: string
  page?: number
  page_size?: number
}
