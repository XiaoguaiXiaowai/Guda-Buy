import http from '@/api/http'
import type { Paginated } from '@/types/catalog'
import type {
  AdminReview,
  AdminReviewQuery,
  PublicReview,
  ReviewEligibility,
  ReviewImage,
  ReviewSubmitPayload,
} from '@/types/review'

export async function fetchProductReviews(
  publicId: string,
  params: { page?: number; page_size?: number } = {},
): Promise<Paginated<PublicReview>> {
  const { data } = await http.get<Paginated<PublicReview>>(`/products/${publicId}/reviews/`, {
    params,
  })
  return data
}

export async function fetchOrderReview(orderNo: string): Promise<ReviewEligibility> {
  const { data } = await http.get<ReviewEligibility>(`/orders/${orderNo}/review/`)
  return data
}

export async function submitOrderReview(
  orderNo: string,
  payload: ReviewSubmitPayload,
): Promise<ReviewEligibility> {
  const { data } = await http.post<ReviewEligibility>(`/orders/${orderNo}/review/`, payload)
  return data
}

export async function uploadReviewImage(reviewId: string, file: File): Promise<ReviewImage> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await http.post<ReviewImage>(`/reviews/${reviewId}/images/`, form)
  return data
}

export async function fetchAdminReviews(query: AdminReviewQuery = {}): Promise<
  Paginated<AdminReview>
> {
  const { data } = await http.get<Paginated<AdminReview>>('/admin/reviews/', { params: query })
  return data
}

export async function approveReview(publicId: string): Promise<AdminReview> {
  const { data } = await http.post<AdminReview>(`/admin/reviews/${publicId}/approve/`)
  return data
}

export async function rejectReview(publicId: string, rejectReason: string): Promise<AdminReview> {
  const { data } = await http.post<AdminReview>(`/admin/reviews/${publicId}/reject/`, {
    reject_reason: rejectReason,
  })
  return data
}
