<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { fetchCategoryTree, fetchProducts, suggestProducts } from '@/api/catalog'
import type { CategoryNode, ProductListItem, ProductSuggestion } from '@/types/catalog'
import { formatPriceRange, resolveImageUrl, toQueryParams } from '@/utils/catalog'

const route = useRoute()
const router = useRouter()

const categories = ref<CategoryNode[]>([])
const products = ref<ProductListItem[]>([])
const total = ref(0)
const loading = ref(false)

const filters = reactive({
  category: '',
  search: '',
  ordering: 'default',
  priceMin: '',
  priceMax: '',
  page: 1,
  pageSize: 12,
})

async function loadCategories() {
  categories.value = await fetchCategoryTree()
}

async function loadProducts() {
  loading.value = true
  try {
    const data = await fetchProducts(
      toQueryParams({
        category: filters.category,
        search: filters.search.trim(),
        ordering: filters.ordering === 'default' ? '' : filters.ordering,
        price_min: filters.priceMin,
        price_max: filters.priceMax,
        page: filters.page,
        page_size: filters.pageSize,
      }),
    )
    products.value = data.results
    total.value = data.count
  } finally {
    loading.value = false
  }
}

function applyFilters() {
  filters.page = 1
  void loadProducts()
}

function selectCategory(publicId: string) {
  filters.category = publicId
  applyFilters()
}

async function querySuggestions(keyword: string, callback: (items: ProductSuggestion[]) => void) {
  if (!keyword.trim()) {
    callback([])
    return
  }
  try {
    callback(await suggestProducts(keyword))
  } catch {
    callback([])
  }
}

function openSuggestion(item: Record<string, unknown>) {
  const suggestion = item as unknown as ProductSuggestion
  if (suggestion.public_id) {
    void router.push({ name: 'product-detail', params: { publicId: suggestion.public_id } })
  }
}

function openProduct(publicId: string) {
  void router.push({ name: 'product-detail', params: { publicId } })
}

function handlePageChange(page: number) {
  filters.page = page
  void loadProducts()
}

watch(
  () => route.params.publicId,
  (publicId) => {
    filters.category = publicId ? String(publicId) : ''
    filters.page = 1
    void loadProducts()
  },
)

onMounted(async () => {
  filters.category = route.params.publicId ? String(route.params.publicId) : ''
  await Promise.all([loadCategories(), loadProducts()])
})
</script>

<template>
  <section class="product-list">
    <header class="product-list__hero">
      <p class="product-list__eyebrow">商品目录</p>
      <h1 class="product-list__title">挑一件喜欢的</h1>
      <p class="product-list__desc">按分类浏览、按价格与销量排序，搜索支持名称联想。</p>
    </header>

    <div class="product-list__layout">
      <aside class="product-list__aside">
        <button
          class="product-list__all"
          :class="{ 'is-active': !filters.category }"
          type="button"
          @click="selectCategory('')"
        >
          全部分类
        </button>
        <div v-for="parent in categories" :key="parent.public_id" class="product-list__group">
          <p class="product-list__group-name">
            {{ parent.name }}
            <span>{{ parent.product_count }}</span>
          </p>
          <button
            v-for="child in parent.children"
            :key="child.public_id"
            class="product-list__child"
            :class="{ 'is-active': filters.category === child.public_id }"
            type="button"
            @click="selectCategory(child.public_id)"
          >
            <span>{{ child.name }}</span>
            <span class="product-list__count">{{ child.product_count }}</span>
          </button>
        </div>
      </aside>

      <div class="product-list__content">
        <div class="product-list__toolbar">
          <el-autocomplete
            v-model="filters.search"
            class="product-list__search"
            :fetch-suggestions="querySuggestions"
            placeholder="搜索商品名称"
            clearable
            value-key="name"
            @select="openSuggestion"
            @keyup.enter="applyFilters"
          >
            <template #default="{ item }">
              <div class="suggest-item">
                <span>{{ item.name }}</span>
                <span class="suggest-item__price">¥{{ item.price_min }}</span>
              </div>
            </template>
          </el-autocomplete>
          <el-button type="primary" @click="applyFilters">搜索</el-button>

          <div class="product-list__price">
            <el-input v-model="filters.priceMin" placeholder="最低价" />
            <span>—</span>
            <el-input v-model="filters.priceMax" placeholder="最高价" />
            <el-button @click="applyFilters">应用</el-button>
          </div>

          <el-select v-model="filters.ordering" class="product-list__sort" @change="applyFilters">
            <el-option label="综合推荐" value="default" />
            <el-option label="价格从低到高" value="price" />
            <el-option label="价格从高到低" value="-price" />
            <el-option label="销量优先" value="sales" />
            <el-option label="最新上架" value="-created_at" />
          </el-select>
        </div>

        <el-skeleton v-if="loading" :rows="6" animated />

        <template v-else>
          <div v-if="products.length" class="product-list__grid">
            <article
              v-for="product in products"
              :key="product.public_id"
              class="product-card"
              @click="openProduct(product.public_id)"
            >
              <div class="product-card__media">
                <img
                  v-if="product.main_image"
                  :src="resolveImageUrl(product.main_image)"
                  :alt="product.name"
                  loading="lazy"
                />
                <span v-else class="product-card__placeholder">{{ product.name.slice(0, 1) }}</span>
              </div>
              <div class="product-card__body">
                <p class="product-card__category">{{ product.category.name }}</p>
                <h2 class="product-card__name">{{ product.name }}</h2>
                <p class="product-card__subtitle">{{ product.subtitle || '精选好物' }}</p>
                <div class="product-card__footer">
                  <strong>{{ formatPriceRange(product.price_min, product.price_max) }}</strong>
                  <span>已售 {{ product.sales_count }}</span>
                </div>
              </div>
            </article>
          </div>
          <el-empty v-else description="该条件下暂无在售商品" />
        </template>

        <el-pagination
          v-if="total > 0"
          class="product-list__pagination"
          layout="prev, pager, next"
          :total="total"
          :page-size="filters.pageSize"
          :current-page="filters.page"
          @current-change="handlePageChange"
        />
      </div>
    </div>
  </section>
</template>

<style scoped lang="scss">
.product-list {
  &__hero {
    max-width: 720px;
    margin-bottom: 28px;
  }

  &__eyebrow {
    color: var(--guda-primary);
    font-size: 13px;
    letter-spacing: 3px;
    text-transform: uppercase;
    margin-bottom: 8px;
  }

  &__title {
    font-size: 34px;
    margin-bottom: 10px;
  }

  &__desc {
    color: var(--guda-text-muted);
    font-size: 14px;
  }

  &__layout {
    display: grid;
    grid-template-columns: 200px minmax(0, 1fr);
    gap: 28px;
    align-items: start;
  }

  &__aside {
    border: 1px solid var(--guda-border);
    border-radius: var(--guda-radius);
    background: var(--guda-surface);
    padding: 16px;
    position: sticky;
    top: 88px;
  }

  &__all,
  &__child {
    width: 100%;
    border: none;
    background: transparent;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    padding: 8px 10px;
    border-radius: 8px;
    color: var(--guda-text);
    font-size: 14px;
    cursor: pointer;
    text-align: left;

    &:hover,
    &.is-active {
      color: var(--guda-primary);
      background: rgba(196, 30, 58, 0.08);
    }
  }

  &__group {
    margin-top: 16px;
  }

  &__group-name {
    display: flex;
    justify-content: space-between;
    font-size: 13px;
    color: var(--guda-text-muted);
    margin-bottom: 4px;
    padding: 0 10px;
  }

  &__count {
    font-size: 12px;
    color: var(--guda-text-muted);
  }

  &__toolbar {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 12px;
    margin-bottom: 20px;
  }

  &__search {
    width: 260px;
  }

  &__price {
    display: flex;
    align-items: center;
    gap: 6px;

    :deep(.el-input) {
      width: 92px;
    }
  }

  &__sort {
    width: 150px;
    margin-left: auto;
  }

  &__grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 20px;
  }

  &__pagination {
    margin-top: 28px;
    justify-content: center;
  }
}

.suggest-item {
  display: flex;
  justify-content: space-between;
  gap: 16px;

  &__price {
    color: var(--guda-primary);
  }
}

.product-card {
  border: 1px solid var(--guda-border);
  border-radius: var(--guda-radius);
  background: var(--guda-surface);
  overflow: hidden;
  cursor: pointer;
  transition:
    transform 0.18s ease,
    box-shadow 0.18s ease;

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 12px 28px rgba(17, 24, 39, 0.08);
  }

  &__media {
    aspect-ratio: 4 / 3;
    background: #f5f5f4;
    display: flex;
    align-items: center;
    justify-content: center;

    img {
      width: 100%;
      height: 100%;
      object-fit: cover;
    }
  }

  &__placeholder {
    font-size: 40px;
    color: #d6d3d1;
    font-weight: 700;
  }

  &__body {
    padding: 14px 16px 16px;
  }

  &__category {
    font-size: 12px;
    color: var(--guda-text-muted);
    margin-bottom: 4px;
  }

  &__name {
    font-size: 15px;
    line-height: 1.5;
    margin-bottom: 4px;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  &__subtitle {
    font-size: 12px;
    color: var(--guda-text-muted);
    margin-bottom: 12px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  &__footer {
    display: flex;
    align-items: baseline;
    justify-content: space-between;

    strong {
      color: var(--guda-primary);
      font-size: 17px;
    }

    span {
      font-size: 12px;
      color: var(--guda-text-muted);
    }
  }
}

@media (max-width: 991px) {
  .product-list {
    &__layout {
      grid-template-columns: 1fr;
    }

    &__aside {
      position: static;
    }

    &__sort {
      margin-left: 0;
    }
  }
}
</style>
