import http from '@/api/http'
import type {
  AdminCategory,
  AdminCategoryPayload,
  AdminProduct,
  AdminProductPayload,
  AdminSku,
  AdminSkuPayload,
  CategoryNode,
  Paginated,
  ProductDetail,
  ProductListItem,
  ProductQuery,
  ProductSuggestion,
} from '@/types/catalog'

export async function fetchCategoryTree(): Promise<CategoryNode[]> {
  const { data } = await http.get<CategoryNode[]>('/categories/tree/')
  return data
}

export async function fetchProducts(
  params: ProductQuery = {},
): Promise<Paginated<ProductListItem>> {
  const { data } = await http.get<Paginated<ProductListItem>>('/products/', { params })
  return data
}

export async function fetchProduct(publicId: string): Promise<ProductDetail> {
  const { data } = await http.get<ProductDetail>(`/products/${publicId}/`)
  return data
}

export async function fetchRelatedProducts(publicId: string): Promise<ProductListItem[]> {
  const { data } = await http.get<ProductListItem[]>(`/products/${publicId}/related/`)
  return data
}

export async function suggestProducts(keyword: string): Promise<ProductSuggestion[]> {
  const { data } = await http.get<ProductSuggestion[]>('/products/suggest/', {
    params: { keyword },
  })
  return data
}

// ---------------------------------------------------------------------------
// 后台
// ---------------------------------------------------------------------------
export async function fetchAdminCategories(): Promise<AdminCategory[]> {
  const { data } = await http.get<AdminCategory[]>('/admin/categories/')
  return data
}

export async function createCategory(payload: AdminCategoryPayload): Promise<AdminCategory> {
  const { data } = await http.post<AdminCategory>('/admin/categories/', payload)
  return data
}

export async function updateCategory(
  publicId: string,
  payload: AdminCategoryPayload,
): Promise<AdminCategory> {
  const { data } = await http.put<AdminCategory>(`/admin/categories/${publicId}/`, payload)
  return data
}

export async function deleteCategory(publicId: string): Promise<void> {
  await http.delete(`/admin/categories/${publicId}/`)
}

export async function fetchAdminProducts(
  params: ProductQuery & { status?: string } = {},
): Promise<Paginated<AdminProduct>> {
  const { data } = await http.get<Paginated<AdminProduct>>('/admin/products/', { params })
  return data
}

export async function fetchAdminProduct(publicId: string): Promise<AdminProduct> {
  const { data } = await http.get<AdminProduct>(`/admin/products/${publicId}/`)
  return data
}

export async function createProduct(payload: AdminProductPayload): Promise<AdminProduct> {
  const { data } = await http.post<AdminProduct>('/admin/products/', payload)
  return data
}

export async function updateProduct(
  publicId: string,
  payload: AdminProductPayload,
): Promise<AdminProduct> {
  const { data } = await http.put<AdminProduct>(`/admin/products/${publicId}/`, payload)
  return data
}

export async function deleteProduct(publicId: string): Promise<void> {
  await http.delete(`/admin/products/${publicId}/`)
}

export async function publishProduct(publicId: string): Promise<AdminProduct> {
  const { data } = await http.post<AdminProduct>(`/admin/products/${publicId}/publish/`)
  return data
}

export async function unpublishProduct(publicId: string): Promise<AdminProduct> {
  const { data } = await http.post<AdminProduct>(`/admin/products/${publicId}/unpublish/`)
  return data
}

export async function fetchAdminSkus(productPublicId: string): Promise<AdminSku[]> {
  const { data } = await http.get<AdminSku[]>(`/admin/products/${productPublicId}/skus/`)
  return data
}

export async function createSku(
  productPublicId: string,
  payload: AdminSkuPayload,
): Promise<AdminSku> {
  const { data } = await http.post<AdminSku>(`/admin/products/${productPublicId}/skus/`, payload)
  return data
}

export async function updateSku(publicId: string, payload: AdminSkuPayload): Promise<AdminSku> {
  const { data } = await http.put<AdminSku>(`/admin/skus/${publicId}/`, payload)
  return data
}

export async function adjustStock(
  skuPublicId: string,
  change: number,
  reason: string,
): Promise<AdminSku> {
  const { data } = await http.patch<AdminSku>(`/admin/skus/${skuPublicId}/stock/`, {
    change,
    reason,
  })
  return data
}

export async function uploadProductImage(
  productPublicId: string,
  file: File,
): Promise<{ public_id: string; image: string; sort_order: number }> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await http.post(`/admin/products/${productPublicId}/images/`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function deleteProductImage(
  productPublicId: string,
  imagePublicId: string,
): Promise<void> {
  await http.delete(`/admin/products/${productPublicId}/images/${imagePublicId}/`)
}
