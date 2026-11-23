<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { fetchProduct, fetchRelatedProducts } from '@/api/catalog'
import { fetchProductReviews } from '@/api/review'
import { useAuthStore } from '@/stores/auth'
import { useCartStore } from '@/stores/cart'
import type { ProductDetail, ProductListItem, Sku } from '@/types/catalog'
import type { PublicReview } from '@/types/review'
import { formatPriceRange, resolveImageUrl, stockTone } from '@/utils/catalog'
import { formatCurrency, formatDateTime } from '@/utils/format'
import { distributionPercent } from '@/utils/review'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const cart = useCartStore()

const product = ref<ProductDetail | null>(null)
const related = ref<ProductListItem[]>([])
const loading = ref(true)
const notFound = ref(false)
const adding = ref(false)
const selectedSkuId = ref('')
const activeImage = ref('')
const reviews = ref<PublicReview[]>([])
const reviewTotal = ref(0)
const reviewPage = ref(1)
const reviewLoading = ref(false)
const reviewPageSize = 5

const selectedSku = computed<Sku | null>(
  () => product.value?.skus.find((sku) => sku.public_id === selectedSkuId.value) ?? null,
)

const gallery = computed(() => {
  const images = product.value?.images.map((item) => item.image) ?? []
  if (product.value?.main_image && !images.includes(product.value.main_image)) {
    images.unshift(product.value.main_image)
  }
  return images
})

const currentPrice = computed(() => {
  if (selectedSku.value) {
    return formatCurrency(selectedSku.value.sale_price)
  }
  return product.value ? formatPriceRange(product.value.price_min, product.value.price_max) : '-'
})

async function loadReviews(publicId: string, page = 1) {
  reviewLoading.value = true
  try {
    const data = await fetchProductReviews(publicId, { page, page_size: reviewPageSize })
    reviews.value = data.results
    reviewTotal.value = data.count
    reviewPage.value = page
  } catch {
    reviews.value = []
    reviewTotal.value = 0
  } finally {
    reviewLoading.value = false
  }
}

function reviewPercent(star: number): number {
  const count = product.value?.review_summary.distribution[String(star)] ?? 0
  return distributionPercent(count, product.value?.review_summary.count ?? 0)
}

function changeReviewPage(page: number) {
  void loadReviews(String(route.params.publicId), page)
}

async function load(publicId: string) {
  loading.value = true
  notFound.value = false
  try {
    product.value = await fetchProduct(publicId)
    activeImage.value = product.value.main_image || product.value.images[0]?.image || ''
    const available = product.value.skus.find((sku) => sku.stock > 0)
    selectedSkuId.value = available?.public_id ?? product.value.skus[0]?.public_id ?? ''
    related.value = await fetchRelatedProducts(publicId)
  } catch {
    product.value = null
    related.value = []
    notFound.value = true
  } finally {
    loading.value = false
  }
  await loadReviews(publicId)
}

function selectSku(sku: Sku) {
  if (sku.stock <= 0) {
    return
  }
  selectedSkuId.value = sku.public_id
}

async function addToCart() {
  if (!selectedSku.value || selectedSku.value.stock <= 0) {
    ElMessage.warning('请选择有库存的规格')
    return
  }
  if (!auth.isAuthenticated) {
    ElMessage.warning('请先登录后加入购物车')
    await router.push({ name: 'login', query: { redirect: route.fullPath } })
    return
  }
  adding.value = true
  try {
    await cart.addItem(selectedSku.value.public_id)
    ElMessage.success('已加入购物车')
  } finally {
    adding.value = false
  }
}

function openProduct(publicId: string) {
  void router.push({ name: 'product-detail', params: { publicId } })
}

watch(
  () => route.params.publicId,
  (publicId) => {
    if (publicId) {
      void load(String(publicId))
    }
  },
)

onMounted(() => {
  void load(String(route.params.publicId))
})
</script>

<template>
  <section class="product-detail">
    <el-skeleton v-if="loading" :rows="8" animated />

    <el-result
      v-else-if="notFound"
      icon="warning"
      title="商品不存在或已下架"
      sub-title="返回商品列表看看其他在售商品。"
    >
      <template #extra>
        <el-button type="primary" @click="router.push({ name: 'product-list' })">
          返回商品列表
        </el-button>
      </template>
    </el-result>

    <template v-else-if="product">
      <div class="product-detail__top">
        <div class="product-detail__gallery">
          <div class="product-detail__main-image">
            <img v-if="activeImage" :src="resolveImageUrl(activeImage)" :alt="product.name" />
            <span v-else>{{ product.name.slice(0, 1) }}</span>
          </div>
          <div v-if="gallery.length > 1" class="product-detail__thumbs">
            <button
              v-for="image in gallery"
              :key="image"
              type="button"
              :class="{ 'is-active': activeImage === image }"
              @click="activeImage = image"
            >
              <img :src="resolveImageUrl(image)" :alt="product.name" loading="lazy" />
            </button>
          </div>
        </div>

        <div class="product-detail__info">
          <p class="product-detail__category">
            {{ product.category.name }}
            <span>已售 {{ product.sales_count }}</span>
          </p>
          <h1>{{ product.name }}</h1>
          <p class="product-detail__subtitle">{{ product.subtitle || 'GUDA 严选' }}</p>

          <div class="product-detail__price">
            <strong>{{ currentPrice }}</strong>
            <del v-if="selectedSku?.original_price">
              {{ formatCurrency(selectedSku.original_price) }}
            </del>
          </div>

          <div class="product-detail__skus">
            <p class="product-detail__label">选择规格</p>
            <div class="product-detail__sku-list">
              <button
                v-for="sku in product.skus"
                :key="sku.public_id"
                type="button"
                class="product-detail__sku"
                :class="{
                  'is-active': sku.public_id === selectedSkuId,
                  'is-disabled': sku.stock <= 0,
                }"
                @click="selectSku(sku)"
              >
                {{ sku.spec_text }}
              </button>
            </div>
            <el-tag
              v-if="selectedSku"
              :type="stockTone(selectedSku.stock_status)"
              effect="light"
              size="small"
            >
              {{ selectedSku.stock_text }}
            </el-tag>
          </div>

          <div class="product-detail__actions">
            <el-button
              type="primary"
              size="large"
              :loading="adding"
              :disabled="!selectedSku || selectedSku.stock <= 0"
              @click="addToCart"
            >
              加入购物车
            </el-button>
            <span class="product-detail__hint">库存以 SKU 维度实时校验，结算与支付将在后续迭代接入。</span>
          </div>
        </div>
      </div>

      <div class="product-detail__section">
        <h2>商品详情</h2>
        <p class="product-detail__description">{{ product.description || '暂无详情描述。' }}</p>
      </div>

      <div class="product-detail__section">
        <h2>用户评价</h2>

        <div v-if="product.review_summary.count" class="review-summary">
          <div class="review-summary__score">
            <strong>{{ product.review_summary.average }}</strong>
            <el-rate
              :model-value="Number(product.review_summary.average)"
              disabled
              allow-half
            />
            <span>{{ product.review_summary.count }} 条已通过评价</span>
          </div>
          <div class="review-summary__bars">
            <div v-for="star in [5, 4, 3, 2, 1]" :key="star" class="review-summary__bar">
              <span>{{ star }} 星</span>
              <el-progress :percentage="reviewPercent(star)" :show-text="false" :stroke-width="8" />
              <span>{{ product.review_summary.distribution[String(star)] ?? 0 }}</span>
            </div>
          </div>
        </div>
        <p v-else class="product-detail__description">暂无已通过审核的评价。</p>

        <div v-loading="reviewLoading" class="review-list">
          <article v-for="item in reviews" :key="item.public_id" class="review-list__item">
            <header class="review-list__head">
              <el-avatar :size="32" :src="item.avatar ? resolveImageUrl(item.avatar) : undefined">
                {{ item.display_name.slice(0, 1) }}
              </el-avatar>
              <strong>{{ item.display_name }}</strong>
              <el-rate :model-value="item.rating" disabled />
              <time>{{ formatDateTime(item.created_at) }}</time>
            </header>
            <p class="review-list__content">{{ item.content }}</p>
            <span class="review-list__spec">{{ item.sku_spec }}</span>
            <div v-if="item.images.length" class="review-list__images">
              <el-image
                v-for="image in item.images"
                :key="image.public_id"
                :src="resolveImageUrl(image.image)"
                :preview-src-list="item.images.map((pic) => resolveImageUrl(pic.image))"
                fit="cover"
                preview-teleported
              />
            </div>
          </article>
        </div>

        <el-pagination
          v-if="reviewTotal > reviewPageSize"
          class="review-pagination"
          layout="prev, pager, next"
          :total="reviewTotal"
          :page-size="reviewPageSize"
          :current-page="reviewPage"
          @current-change="changeReviewPage"
        />
      </div>

      <div v-if="related.length" class="product-detail__section">
        <h2>相关推荐</h2>
        <div class="product-detail__related">
          <article
            v-for="item in related"
            :key="item.public_id"
            class="related-card"
            @click="openProduct(item.public_id)"
          >
            <div class="related-card__media">
              <img
                v-if="item.main_image"
                :src="resolveImageUrl(item.main_image)"
                :alt="item.name"
                loading="lazy"
              />
              <span v-else>{{ item.name.slice(0, 1) }}</span>
            </div>
            <p>{{ item.name }}</p>
            <strong>{{ formatPriceRange(item.price_min, item.price_max) }}</strong>
          </article>
        </div>
      </div>
    </template>
  </section>
</template>

<style scoped lang="scss">
.product-detail {
  &__top {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
    gap: 48px;
    margin-bottom: 48px;
  }

  &__main-image {
    aspect-ratio: 4 / 3;
    border-radius: var(--guda-radius);
    background: #f5f5f4;
    border: 1px solid var(--guda-border);
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    font-size: 64px;
    color: #d6d3d1;
    font-weight: 700;

    img {
      width: 100%;
      height: 100%;
      object-fit: cover;
    }
  }

  &__thumbs {
    display: flex;
    gap: 10px;
    margin-top: 12px;

    button {
      width: 64px;
      height: 64px;
      padding: 0;
      border: 1px solid var(--guda-border);
      border-radius: 8px;
      overflow: hidden;
      background: #fff;
      cursor: pointer;

      &.is-active {
        border-color: var(--guda-primary);
      }

      img {
        width: 100%;
        height: 100%;
        object-fit: cover;
      }
    }
  }

  &__category {
    display: flex;
    justify-content: space-between;
    color: var(--guda-text-muted);
    font-size: 13px;
    margin-bottom: 10px;
  }

  h1 {
    font-size: 30px;
    line-height: 1.3;
    margin-bottom: 10px;
  }

  &__subtitle {
    color: var(--guda-text-muted);
    font-size: 14px;
    margin-bottom: 22px;
  }

  &__price {
    display: flex;
    align-items: baseline;
    gap: 12px;
    padding: 16px 20px;
    background: rgba(196, 30, 58, 0.06);
    border-radius: var(--guda-radius);
    margin-bottom: 24px;

    strong {
      color: var(--guda-primary);
      font-size: 30px;
    }

    del {
      color: var(--guda-text-muted);
      font-size: 14px;
    }
  }

  &__label {
    font-size: 13px;
    color: var(--guda-text-muted);
    margin-bottom: 10px;
  }

  &__skus {
    margin-bottom: 28px;
  }

  &__sku-list {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin-bottom: 12px;
  }

  &__sku {
    padding: 8px 16px;
    border: 1px solid var(--guda-border);
    border-radius: 999px;
    background: #fff;
    cursor: pointer;
    font-size: 14px;

    &.is-active {
      border-color: var(--guda-primary);
      color: var(--guda-primary);
      background: rgba(196, 30, 58, 0.06);
    }

    &.is-disabled {
      color: #c0c4cc;
      cursor: not-allowed;
      text-decoration: line-through;
    }
  }

  &__actions {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  &__hint {
    font-size: 12px;
    color: var(--guda-text-muted);
  }

  &__section {
    border-top: 1px solid var(--guda-border);
    padding-top: 28px;
    margin-bottom: 32px;

    h2 {
      font-size: 20px;
      margin-bottom: 14px;
    }
  }

  &__description {
    color: var(--guda-text-muted);
    line-height: 1.9;
    white-space: pre-wrap;
    font-size: 14px;
  }

  &__related {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    gap: 18px;
  }
}

.review-summary {
  display: grid;
  grid-template-columns: minmax(0, 200px) minmax(0, 1fr);
  gap: 28px;
  align-items: center;
  margin: 18px 0 24px;

  &__score {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 6px;

    strong {
      font-size: 40px;
      line-height: 1;
      color: var(--guda-primary);
    }

    span {
      color: var(--guda-text-muted);
      font-size: 12px;
    }
  }

  &__bars {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  &__bar {
    display: grid;
    grid-template-columns: 40px minmax(0, 1fr) 32px;
    align-items: center;
    gap: 10px;
    color: var(--guda-text-muted);
    font-size: 12px;
  }
}

.review-list {
  min-height: 60px;

  &__item {
    padding: 18px 0;
    border-bottom: 1px solid var(--guda-border);

    &:last-child {
      border-bottom: none;
    }
  }

  &__head {
    display: flex;
    align-items: center;
    gap: 10px;

    strong {
      font-size: 14px;
    }

    time {
      margin-left: auto;
      color: var(--guda-text-muted);
      font-size: 12px;
    }
  }

  &__content {
    margin: 10px 0 6px;
    line-height: 1.7;
    white-space: pre-wrap;
  }

  &__spec {
    color: var(--guda-text-muted);
    font-size: 12px;
  }

  &__images {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 10px;

    :deep(.el-image) {
      width: 84px;
      height: 84px;
      border-radius: 8px;
      overflow: hidden;
      cursor: zoom-in;
    }
  }
}

.review-pagination {
  margin-top: 16px;
  justify-content: center;
}

.related-card {
  border: 1px solid var(--guda-border);
  border-radius: var(--guda-radius);
  overflow: hidden;
  background: var(--guda-surface);
  cursor: pointer;
  padding-bottom: 14px;
  transition: box-shadow 0.18s ease;

  &:hover {
    box-shadow: 0 10px 24px rgba(17, 24, 39, 0.08);
  }

  &__media {
    aspect-ratio: 4 / 3;
    background: #f5f5f4;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #d6d3d1;
    font-size: 32px;
    margin-bottom: 10px;

    img {
      width: 100%;
      height: 100%;
      object-fit: cover;
    }
  }

  p {
    font-size: 14px;
    padding: 0 12px;
    margin-bottom: 6px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  strong {
    padding: 0 12px;
    color: var(--guda-primary);
    font-size: 15px;
  }
}

@media (max-width: 767px) {
  .product-detail {
    &__top {
      grid-template-columns: 1fr;
      gap: 24px;
    }

    h1 {
      font-size: 24px;
    }
  }
}
</style>
