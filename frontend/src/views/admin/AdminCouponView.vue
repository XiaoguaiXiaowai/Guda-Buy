<script setup lang="ts">
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'

import { fetchAdminCategories, fetchAdminProducts } from '@/api/catalog'
import { createCoupon, fetchAdminCoupons, updateCoupon } from '@/api/coupon'
import type { AdminCategory } from '@/types/catalog'
import type {
  AdminCoupon,
  CouponScopeRef,
  CouponScopeType,
  CouponStatus,
  CouponType,
  CouponWritePayload,
} from '@/types/coupon'
import { toQueryParams } from '@/utils/catalog'
import { couponConditionLabel, couponStatusTone, couponValueLabel } from '@/utils/coupon'
import { formatDateTime } from '@/utils/format'

const coupons = ref<AdminCoupon[]>([])
const total = ref(0)
const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const editing = ref<AdminCoupon | null>(null)
const formRef = ref<FormInstance>()

const filters = reactive({
  status: '' as CouponStatus | '',
  couponType: '' as CouponType | '',
  keyword: '',
  page: 1,
  pageSize: 10,
})

const categories = ref<AdminCategory[]>([])
const productOptions = ref<CouponScopeRef[]>([])
const productLoading = ref(false)

interface CouponForm {
  name: string
  coupon_type: CouponType
  value: string
  min_amount: string
  total_quantity: number
  per_user_limit: number
  scope_type: CouponScopeType
  scope_category_public_ids: string[]
  scope_product_public_ids: string[]
  valid_from: string
  valid_to: string
  status: CouponStatus
}

const emptyForm = (): CouponForm => ({
  name: '',
  coupon_type: 'FIXED',
  value: '10.00',
  min_amount: '0.00',
  total_quantity: 100,
  per_user_limit: 1,
  scope_type: 'ALL',
  scope_category_public_ids: [],
  scope_product_public_ids: [],
  valid_from: '',
  valid_to: '',
  status: 'DRAFT',
})

const form = reactive<CouponForm>(emptyForm())

const rules: FormRules = {
  name: [{ required: true, message: '请输入券名称', trigger: 'blur' }],
  coupon_type: [{ required: true, message: '请选择券类型', trigger: 'change' }],
  total_quantity: [{ required: true, message: '请输入发行总量', trigger: 'blur' }],
  valid_from: [{ required: true, message: '请选择生效时间', trigger: 'change' }],
  valid_to: [{ required: true, message: '请选择失效时间', trigger: 'change' }],
}

function toPickerValue(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return ''
  }
  const pad = (input: number) => String(input).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(
    date.getHours(),
  )}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

async function load(): Promise<void> {
  loading.value = true
  try {
    const data = await fetchAdminCoupons(
      toQueryParams({
        status: filters.status,
        coupon_type: filters.couponType,
        keyword: filters.keyword.trim(),
        page: filters.page,
        page_size: filters.pageSize,
      }),
    )
    coupons.value = data.results
    total.value = data.count
  } finally {
    loading.value = false
  }
}

function applyFilters(): void {
  filters.page = 1
  void load()
}

async function searchProducts(keyword: string): Promise<void> {
  productLoading.value = true
  try {
    const data = await fetchAdminProducts(
      toQueryParams({ search: keyword, page: 1, page_size: 20 }),
    )
    productOptions.value = data.results.map((product) => ({
      public_id: product.public_id,
      name: product.name,
    }))
  } finally {
    productLoading.value = false
  }
}

function openCreate(): void {
  editing.value = null
  Object.assign(form, emptyForm())
  dialogVisible.value = true
  void formRef.value?.clearValidate()
}

function openEdit(row: AdminCoupon): void {
  if (row.claimed_quantity > 0) {
    ElMessage.warning('券已开始发放，不能修改')
    return
  }
  editing.value = row
  productOptions.value = [...row.scope_products]
  Object.assign(form, {
    name: row.name,
    coupon_type: row.coupon_type,
    value: row.coupon_type === 'FREE_SHIPPING' ? '0.00' : row.value,
    min_amount: row.min_amount,
    total_quantity: row.total_quantity,
    per_user_limit: row.per_user_limit,
    scope_type: row.scope_type,
    scope_category_public_ids: row.scope_categories.map((item) => item.public_id),
    scope_product_public_ids: row.scope_products.map((item) => item.public_id),
    valid_from: toPickerValue(row.valid_from),
    valid_to: toPickerValue(row.valid_to),
    status: row.status,
  })
  dialogVisible.value = true
  void formRef.value?.clearValidate()
}

function onScopeTypeChange(): void {
  form.scope_category_public_ids = []
  form.scope_product_public_ids = []
}

async function submit(): Promise<void> {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) {
    return
  }
  if (form.valid_from >= form.valid_to) {
    ElMessage.warning('失效时间必须晚于生效时间')
    return
  }
  if (form.scope_type === 'CATEGORY' && !form.scope_category_public_ids.length) {
    ElMessage.warning('请选择适用分类')
    return
  }
  if (form.scope_type === 'PRODUCT' && !form.scope_product_public_ids.length) {
    ElMessage.warning('请选择适用商品')
    return
  }

  const payload: CouponWritePayload = {
    name: form.name.trim(),
    coupon_type: form.coupon_type,
    value: form.coupon_type === 'FREE_SHIPPING' ? '0.00' : form.value,
    min_amount: form.min_amount || '0.00',
    total_quantity: form.total_quantity,
    per_user_limit: form.per_user_limit,
    scope_type: form.scope_type,
    scope_category_public_ids: form.scope_type === 'CATEGORY' ? form.scope_category_public_ids : [],
    scope_product_public_ids: form.scope_type === 'PRODUCT' ? form.scope_product_public_ids : [],
    valid_from: form.valid_from,
    valid_to: form.valid_to,
    status: form.status,
  }

  saving.value = true
  try {
    if (editing.value) {
      await updateCoupon(editing.value.public_id, payload)
      ElMessage.success('优惠券已更新')
    } else {
      await createCoupon(payload)
      ElMessage.success('优惠券已创建')
    }
    dialogVisible.value = false
    await load()
  } finally {
    saving.value = false
  }
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
        <p class="admin-page__eyebrow">营销后台</p>
        <h1>优惠券管理</h1>
      </div>
      <div class="admin-page__actions">
        <el-button type="primary" @click="openCreate">新建优惠券</el-button>
      </div>
    </header>

    <div class="admin-page__filters">
      <el-select v-model="filters.status" placeholder="全部状态" clearable @change="applyFilters">
        <el-option label="草稿" value="DRAFT" />
        <el-option label="进行中" value="ACTIVE" />
        <el-option label="已停止" value="STOPPED" />
      </el-select>
      <el-select
        v-model="filters.couponType"
        placeholder="全部类型"
        clearable
        @change="applyFilters"
      >
        <el-option label="满减" value="FIXED" />
        <el-option label="折扣" value="DISCOUNT" />
        <el-option label="免邮" value="FREE_SHIPPING" />
      </el-select>
      <el-input
        v-model="filters.keyword"
        placeholder="搜索券名称"
        clearable
        class="admin-page__search"
        @keyup.enter="applyFilters"
      />
      <el-button type="primary" @click="applyFilters">查询</el-button>
    </div>

    <el-table v-loading="loading" :data="coupons" border stripe>
      <el-table-column prop="name" label="券名称" min-width="160" />
      <el-table-column label="优惠" min-width="150">
        <template #default="{ row }">
          <div class="admin-page__cell">
            <strong>{{ couponValueLabel(row) }}</strong>
            <span>{{ couponConditionLabel(row.min_amount) }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="scope_summary" label="适用范围" min-width="150" />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="couponStatusTone(row.status)" size="small">
            {{ row.status_text }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="领取 / 总量" width="120">
        <template #default="{ row }">
          {{ row.claimed_quantity }} / {{ row.total_quantity }}
        </template>
      </el-table-column>
      <el-table-column prop="used_quantity" label="使用量" width="90" />
      <el-table-column label="有效期" min-width="190">
        <template #default="{ row }">
          {{ formatDateTime(row.valid_from) }} ~ {{ formatDateTime(row.valid_to) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <el-button
            link
            type="primary"
            :disabled="row.claimed_quantity > 0"
            :title="row.claimed_quantity > 0 ? '已开始发放，不能修改' : ''"
            @click="openEdit(row)"
          >
            编辑
          </el-button>
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

    <el-dialog
      v-model="dialogVisible"
      :title="editing ? '编辑优惠券' : '新建优惠券'"
      width="640px"
      destroy-on-close
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="96px">
        <el-form-item label="券名称" prop="name">
          <el-input v-model="form.name" maxlength="60" show-word-limit />
        </el-form-item>
        <el-form-item label="券类型" prop="coupon_type">
          <el-radio-group v-model="form.coupon_type">
            <el-radio-button value="FIXED">满减</el-radio-button>
            <el-radio-button value="DISCOUNT">折扣</el-radio-button>
            <el-radio-button value="FREE_SHIPPING">免邮</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item
          v-if="form.coupon_type !== 'FREE_SHIPPING'"
          :label="form.coupon_type === 'DISCOUNT' ? '折扣率' : '面额'"
        >
          <el-input v-model="form.value" placeholder="满减填 20.00；折扣填 0.90" />
        </el-form-item>
        <el-form-item label="使用门槛">
          <el-input v-model="form.min_amount" placeholder="0 表示无门槛" />
        </el-form-item>
        <el-form-item label="发行总量" prop="total_quantity">
          <el-input-number v-model="form.total_quantity" :min="1" :max="1000000" />
        </el-form-item>
        <el-form-item label="每人限领">
          <el-input-number v-model="form.per_user_limit" :min="1" :max="100" />
        </el-form-item>
        <el-form-item label="适用范围">
          <el-select v-model="form.scope_type" @change="onScopeTypeChange">
            <el-option label="全场通用" value="ALL" />
            <el-option label="指定分类" value="CATEGORY" />
            <el-option label="指定商品" value="PRODUCT" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="form.scope_type === 'CATEGORY'" label="适用分类">
          <el-select
            v-model="form.scope_category_public_ids"
            multiple
            filterable
            placeholder="选择分类"
          >
            <el-option
              v-for="category in categories.filter((item) => item.level === 2)"
              :key="category.public_id"
              :label="category.name"
              :value="category.public_id"
            />
          </el-select>
        </el-form-item>
        <el-form-item v-if="form.scope_type === 'PRODUCT'" label="适用商品">
          <el-select
            v-model="form.scope_product_public_ids"
            multiple
            filterable
            remote
            reserve-keyword
            :remote-method="searchProducts"
            :loading="productLoading"
            placeholder="输入商品名称搜索"
          >
            <el-option
              v-for="product in productOptions"
              :key="product.public_id"
              :label="product.name"
              :value="product.public_id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="生效时间" prop="valid_from">
          <el-date-picker
            v-model="form.valid_from"
            type="datetime"
            value-format="YYYY-MM-DDTHH:mm:ss"
            placeholder="选择生效时间"
          />
        </el-form-item>
        <el-form-item label="失效时间" prop="valid_to">
          <el-date-picker
            v-model="form.valid_to"
            type="datetime"
            value-format="YYYY-MM-DDTHH:mm:ss"
            placeholder="选择失效时间"
          />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="form.status">
            <el-option label="草稿" value="DRAFT" />
            <el-option label="进行中" value="ACTIVE" />
            <el-option label="已停止" value="STOPPED" />
          </el-select>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">保存</el-button>
      </template>
    </el-dialog>
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

  &__pagination {
    margin-top: 18px;
    justify-content: flex-end;
  }
}
</style>
