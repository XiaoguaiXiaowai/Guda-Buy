export type CouponType = 'FIXED' | 'DISCOUNT' | 'FREE_SHIPPING'
export type CouponScopeType = 'ALL' | 'CATEGORY' | 'PRODUCT'
export type CouponStatus = 'DRAFT' | 'ACTIVE' | 'STOPPED'
export type UserCouponStatus = 'UNUSED' | 'LOCKED' | 'USED' | 'EXPIRED'

export interface CouponBrief {
  public_id: string
  name: string
  coupon_type: CouponType
  coupon_type_text: string
  value: string
  min_amount: string
  per_user_limit: number
  scope_type: CouponScopeType
  scope_text: string
  scope_summary: string
  total_quantity: number
  claimed_quantity: number
  valid_from: string
  valid_to: string
  status: CouponStatus
  status_text: string
}

export interface CouponEvaluation extends CouponBrief {
  user_coupon_id: string
  claimed_at: string
  expires_at: string
  usable: boolean
  reason: string
  eligible_amount: string
  discount_amount: string
  shipping_amount: string
  payable_amount: string
}

export interface AvailableCoupon extends CouponBrief {
  claimed_by_me: number
  can_claim: boolean
  reason: string
}

export interface UserCoupon {
  public_id: string
  status: UserCouponStatus
  status_text: string
  claimed_at: string
  used_at: string | null
  expires_at: string
  order_no: string
  coupon: CouponBrief
}

export interface MyCoupons {
  unused: UserCoupon[]
  used: UserCoupon[]
  expired: UserCoupon[]
  counts: {
    unused: number
    used: number
    expired: number
  }
}

export interface CouponScopeRef {
  public_id: string
  name: string
}

export interface AdminCoupon extends CouponBrief {
  used_quantity: number
  scope_categories: CouponScopeRef[]
  scope_products: CouponScopeRef[]
  created_at: string
  updated_at: string
}

export interface CouponWritePayload {
  name: string
  coupon_type: CouponType
  value?: string | null
  min_amount?: string
  total_quantity: number
  per_user_limit?: number
  scope_type: CouponScopeType
  scope_category_public_ids?: string[]
  scope_product_public_ids?: string[]
  valid_from: string
  valid_to: string
  status?: CouponStatus
}

export interface AdminCouponQuery {
  status?: CouponStatus | ''
  coupon_type?: CouponType | ''
  keyword?: string
  page?: number
  page_size?: number
}

export interface OrderCoupon {
  public_id: string
  status: UserCouponStatus
  status_text: string
  name: string
  coupon_type: CouponType
  coupon_type_text: string
  value: string
}

export interface OrderCouponTrial {
  order_no: string
  items_amount: string
  coupons: CouponEvaluation[]
  coupon: OrderCoupon | null
}
