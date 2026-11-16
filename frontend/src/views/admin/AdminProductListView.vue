<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import {
  deleteProduct,
  fetchAdminCategories,
  fetchAdminProducts,
  publishProduct,
  unpublishProduct,
} from '@/api/catalog'
import type { AdminCategory, AdminProduct, ProductStatus } from '@/types/catalog'
import {
  formatPriceRange,
  productStatusLabel,
  productStatusTone,
  resolveImageUrl,
  toQueryParams,
} from '@/utils/catalog'
import { formatDateTime } from '@/utils/format'

const router = useRouter()

const products = ref<AdminProduct[]>([])
const categories = ref<AdminCategory[]>([])
const total = ref(0)
const loading = ref(false)

const filters = reactive({
  status: '',
  category: '',
  search: '',
  page: 1,
  pageSize: 10,
})

async function load() {
  loading.value = true
  try {
    const data = await fetchAdminProducts(
      toQueryParams({
        status: filters.status,
        category: filters.category,
        search: filters.search.trim(),
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
  void load()
}

async function toggleSale(product: AdminProduct) {
  if (product.status === 'ON_SALE') {
    const confirmed = await ElMessageBox.confirm(
      `确定下架「${product.name}」吗？下架后前台立即不可见。`,
      '下架商品',
      { type: 'warning', confirmButtonText: '下架', cancelButtonText: '取消' },
    ).catch(() => false)
    if (!confirmed) {
      return
    }
    await unpublishProduct(product.public_id)
    ElMessage.success('商品已下架')
  } else {
    if (product.sku_count === 0) {
      ElMessage.warning('至少创建一个在售 SKU 后才能上架')
      return
    }
    await publishProduct(product.public_id)
    ElMessage.success('商品已上架')
  }
  await load()
}

async function remove(product: AdminProduct) {
  const confirmed = await ElMessageBox.confirm(
    `确定删除「${product.name}」吗？将执行软删除并从前台移除。`,
    '删除商品',
    { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
  ).catch(() => false)
  if (!confirmed) {
    return
  }
  await deleteProduct(product.public_id)
  ElMessage.success('商品已删除')
  await load()
}

function editProduct(publicId: string) {
  void router.push({ name: 'admin-product-edit', params: { publicId } })
}

onMounted(async () => {
  categories.value = await fetchAdminCategories()
  await load()
})
</script>

<template>
  <section class="admin-page">
    <header class="admin-page__header">
      <div>
        <p class="admin-page__eyebrow">商品后台</p>
        <h1>商品管理</h1>
      </div>
      <div class="admin-page__actions">
        <el-button @click="router.push({ name: 'admin-categories' })">分类管理</el-button>
        <el-button type="primary" @click="router.push({ name: 'admin-product-create' })">
          新建商品
        </el-button>
      </div>
    </header>

    <div class="admin-page__filters">
      <el-select v-model="filters.status" placeholder="全部状态" clearable @change="applyFilters">
        <el-option label="草稿" value="DRAFT" />
        <el-option label="在售" value="ON_SALE" />
        <el-option label="已下架" value="OFF_SALE" />
      </el-select>
      <el-select
        v-model="filters.category"
        placeholder="全部分类"
        clearable
        filterable
        @change="applyFilters"
      >
        <el-option
          v-for="category in categories.filter((item) => item.level === 2)"
          :key="category.public_id"
          :label="category.name"
          :value="category.public_id"
        />
      </el-select>
      <el-input
        v-model="filters.search"
        placeholder="搜索商品名称"
        clearable
        class="admin-page__search"
        @keyup.enter="applyFilters"
      />
      <el-button type="primary" @click="applyFilters">查询</el-button>
    </div>

    <el-table v-loading="loading" :data="products" border stripe>
      <el-table-column label="主图" width="90">
        <template #default="{ row }">
          <div class="admin-page__thumb">
            <img v-if="row.main_image" :src="resolveImageUrl(row.main_image)" :alt="row.name" />
            <span v-else>无图</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="name" label="商品名称" min-width="200" />
      <el-table-column label="分类" min-width="120">
        <template #default="{ row }">{{ row.category.name }}</template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="productStatusTone(row.status as ProductStatus)" size="small">
            {{ productStatusLabel(row.status as ProductStatus) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="价格区间" width="150">
        <template #default="{ row }">
          {{ formatPriceRange(row.price_min, row.price_max) }}
        </template>
      </el-table-column>
      <el-table-column prop="sku_count" label="SKU" width="80" />
      <el-table-column prop="stock_total" label="库存" width="80" />
      <el-table-column label="更新时间" width="160">
        <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="210" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="editProduct(row.public_id)">编辑</el-button>
          <el-button link type="primary" @click="toggleSale(row)">
            {{ row.status === 'ON_SALE' ? '下架' : '上架' }}
          </el-button>
          <el-button link type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-if="total > 0"
      class="admin-page__pagination"
      layout="total, prev, pager, next"
      :total="total"
      :page-size="filters.pageSize"
      :current-page="filters.page"
      @current-change="
        (page: number) => {
          filters.page = page
          load()
        }
      "
    />
  </section>
</template>

<style scoped lang="scss">
.admin-page {
  &__header {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 20px;
  }

  &__eyebrow {
    color: var(--guda-text-muted);
    font-size: 12px;
    letter-spacing: 2px;
    margin-bottom: 6px;
  }

  h1 {
    font-size: 26px;
  }

  &__actions {
    display: flex;
    gap: 8px;
  }

  &__filters {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin-bottom: 16px;

    :deep(.el-select) {
      width: 150px;
    }
  }

  &__search {
    width: 220px;
  }

  &__thumb {
    width: 54px;
    height: 54px;
    border-radius: 6px;
    background: #f5f5f4;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    color: var(--guda-text-muted);
    overflow: hidden;

    img {
      width: 100%;
      height: 100%;
      object-fit: cover;
    }
  }

  &__pagination {
    margin-top: 18px;
    justify-content: flex-end;
  }
}
</style>
