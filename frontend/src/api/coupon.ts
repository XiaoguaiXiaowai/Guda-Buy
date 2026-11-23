import http from '@/api/http'
import type { Paginated } from '@/types/catalog'
import type {
  AdminCoupon,
  AdminCouponQuery,
  AvailableCoupon,
  CouponWritePayload,
  MyCoupons,
  OrderCouponTrial,
  UserCoupon,
} from '@/types/coupon'

export async function fetchAvailableCoupons(): Promise<AvailableCoupon[]> {
  const { data } = await http.get<AvailableCoupon[]>('/coupons/available/')
  return data
}

export async function claimCoupon(publicId: string): Promise<UserCoupon> {
  const { data } = await http.post<UserCoupon>(`/coupons/${publicId}/claim/`)
  return data
}

export async function fetchMyCoupons(): Promise<MyCoupons> {
  const { data } = await http.get<MyCoupons>('/users/me/coupons/')
  return data
}

export async function fetchOrderCoupons(orderNo: string): Promise<OrderCouponTrial> {
  const { data } = await http.get<OrderCouponTrial>(`/orders/${orderNo}/coupons/`)
  return data
}

export async function fetchAdminCoupons(
  query: AdminCouponQuery = {},
): Promise<Paginated<AdminCoupon>> {
  const { data } = await http.get<Paginated<AdminCoupon>>('/admin/coupons/', { params: query })
  return data
}

export async function createCoupon(payload: CouponWritePayload): Promise<AdminCoupon> {
  const { data } = await http.post<AdminCoupon>('/admin/coupons/', payload)
  return data
}

export async function updateCoupon(
  publicId: string,
  payload: Partial<CouponWritePayload>,
): Promise<AdminCoupon> {
  const { data } = await http.patch<AdminCoupon>(`/admin/coupons/${publicId}/`, payload)
  return data
}
