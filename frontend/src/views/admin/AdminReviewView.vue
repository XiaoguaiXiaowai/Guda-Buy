<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'

import { approveReview, fetchAdminReviews, rejectReview } from '@/api/review'
import type { AdminReview, ReviewStatus } from '@/types/review'
import { resolveImageUrl, toQueryParams } from '@/utils/catalog'
import { formatDateTime } from '@/utils/format'
import { reviewStatusLabel, reviewStatusTone } from '@/utils/review'

const reviews = ref<AdminReview[]>([])
const total = ref(0)
const loading = ref(false)
const actingId = ref('')

const filters = reactive({
  status: '' as ReviewStatus | '',
  rating: '' as number | '',
  keyword: '',
  page: 1,
  pageSize: 10,
})

async function load(): Promise<void> {
  loading.value = true
  try {
    const data = await fetchAdminReviews(
      toQueryParams({
        status: filters.status,
        rating: filters.rating,
        keyword: filters.keyword.trim(),
        page: filters.page,
        page_size: filters.pageSize,
      }),
    )
    reviews.value = data.results
    total.value = data.count
  } finally {
    loading.value = false
  }
}

function applyFilters(): void {
  filters.page = 1
  void load()
}

function changePage(page: number): void {
  filters.page = page
  void load()
}

function previewList(row: AdminReview): string[] {
  return row.images.map((item) => resolveImageUrl(item.image))
}

async function approve(row: AdminReview): Promise<void> {
  try {
    await ElMessageBox.confirm(`确认通过订单 ${row.order_no} 的评价？通过后将在商品详情展示。`, '审核通过', {
      confirmButtonText: '通过',
      cancelButtonText: '取消',
      type: 'success',
    })
  } catch {
    return
  }
  actingId.value = row.public_id
  try {
    await approveReview(row.public_id)
    ElMessage.success('评价已通过审核')
    await load()
  } finally {
    actingId.value = ''
  }
}

async function reject(row: AdminReview): Promise<void> {
  let reason = ''
  try {
    const result = await ElMessageBox.prompt('请输入驳回原因（1–100 字），用户可修改后重新提交。', '驳回评价', {
      confirmButtonText: '驳回',
      cancelButtonText: '取消',
      inputType: 'textarea',
      inputPlaceholder: '例如：内容与商品无关',
      inputValidator: (value: string) => {
        const text = (value || '').trim()
        if (!text) {
          return '驳回原因必填'
        }
        return text.length <= 100 || '驳回原因不能超过 100 字'
      },
    })
    reason = String(result.value || '').trim()
  } catch {
    return
  }
  actingId.value = row.public_id
  try {
    await rejectReview(row.public_id, reason)
    ElMessage.success('评价已驳回')
    await load()
  } finally {
    actingId.value = ''
  }
}

onMounted(() => {
  void load()
})
</script>

<template>
  <section class="admin-page">
    <header class="admin-page__header">
      <div>
        <p class="admin-page__eyebrow">评价后台</p>
        <h1>评价审核</h1>
      </div>
    </header>

    <div class="admin-page__filters">
      <el-select v-model="filters.status" placeholder="全部状态" clearable @change="applyFilters">
        <el-option label="待审核" value="PENDING" />
        <el-option label="已通过" value="APPROVED" />
        <el-option label="已驳回" value="REJECTED" />
      </el-select>
      <el-select v-model="filters.rating" placeholder="全部星级" clearable @change="applyFilters">
        <el-option v-for="star in [5, 4, 3, 2, 1]" :key="star" :label="`${star} 星`" :value="star" />
      </el-select>
      <el-input
        v-model="filters.keyword"
        placeholder="订单号 / 商品 / 内容"
        clearable
        class="admin-page__search"
        @keyup.enter="applyFilters"
      />
      <el-button type="primary" @click="applyFilters">查询</el-button>
    </div>

    <el-table v-loading="loading" :data="reviews" border stripe>
      <el-table-column label="订单 / 商品" min-width="220">
        <template #default="{ row }">
          <div class="admin-page__cell">
            <strong>{{ row.order_no }}</strong>
            <span>{{ row.product.name }} · {{ row.sku_spec }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="用户" min-width="150">
        <template #default="{ row }">
          <div class="admin-page__cell">
            <strong>{{ row.user.nickname || row.user.username }}</strong>
            <span>
              {{ row.user.username }}
              <el-tag v-if="row.is_anonymous" size="small" type="info">匿名</el-tag>
            </span>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="评分" width="150">
        <template #default="{ row }">
          <el-rate :model-value="row.rating" disabled />
        </template>
      </el-table-column>
      <el-table-column prop="content" label="评价内容" min-width="240" show-overflow-tooltip />
      <el-table-column label="图片" width="150">
        <template #default="{ row }">
          <div v-if="row.images.length" class="admin-page__images">
            <el-image
              v-for="image in row.images"
              :key="image.public_id"
              :src="resolveImageUrl(image.image)"
              :preview-src-list="previewList(row)"
              fit="cover"
              preview-teleported
            />
          </div>
          <span v-else class="admin-page__muted">无</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <el-tag :type="reviewStatusTone(row.status)">
            {{ reviewStatusLabel(row.status, row.status_text) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="提交时间" width="170">
        <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <template v-if="row.status === 'PENDING'">
            <el-button
              size="small"
              type="success"
              :loading="actingId === row.public_id"
              @click="approve(row)"
            >
              通过
            </el-button>
            <el-button
              size="small"
              type="danger"
              :loading="actingId === row.public_id"
              @click="reject(row)"
            >
              驳回
            </el-button>
          </template>
          <span v-else-if="row.status === 'REJECTED'" class="admin-page__muted">
            {{ row.reject_reason || '已驳回' }}
          </span>
          <span v-else class="admin-page__muted">已处理</span>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-if="total > filters.pageSize"
      class="admin-page__pagination"
      layout="total, prev, pager, next"
      :total="total"
      :page-size="filters.pageSize"
      :current-page="filters.page"
      @current-change="changePage"
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
    width: 240px;
  }

  &__cell {
    display: flex;
    flex-direction: column;
    gap: 2px;

    strong {
      color: var(--guda-primary);
    }

    span {
      color: var(--guda-text-muted);
      font-size: 12px;
    }
  }

  &__images {
    display: flex;
    gap: 4px;

    :deep(.el-image) {
      width: 40px;
      height: 40px;
      border-radius: 4px;
      overflow: hidden;
      cursor: zoom-in;
    }
  }

  &__muted {
    color: var(--guda-text-muted);
    font-size: 12px;
  }

  &__pagination {
    margin-top: 18px;
    justify-content: flex-end;
  }
}
</style>
