<script setup lang="ts">
import type { FormInstance, FormRules, UploadRequestOptions } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import {
  adjustStock,
  createProduct,
  createSku,
  deleteProductImage,
  fetchAdminCategories,
  fetchAdminProduct,
  fetchAdminSkus,
  publishProduct,
  unpublishProduct,
  updateProduct,
  updateSku,
  uploadProductImage,
} from '@/api/catalog'
import type {
  AdminCategory,
  AdminProduct,
  AdminSku,
  AdminSkuPayload,
  ProductStatus,
  SkuStatus,
} from '@/types/catalog'
import {
  formatPriceRange,
  productStatusLabel,
  productStatusTone,
  resolveImageUrl,
} from '@/utils/catalog'
import { formatCurrency } from '@/utils/format'

const route = useRoute()
const router = useRouter()

const productId = computed(() => (route.params.publicId ? String(route.params.publicId) : ''))
const isNew = computed(() => !productId.value)

const categories = ref<AdminCategory[]>([])
const product = ref<AdminProduct | null>(null)
const skus = ref<AdminSku[]>([])
const loading = ref(false)
const saving = ref(false)
const uploading = ref(false)
const formRef = ref<FormInstance>()

const form = reactive({
  category_public_id: '',
  name: '',
  subtitle: '',
  description: '',
  sort_weight: 0,
})

const rules: FormRules = {
  category_public_id: [{ required: true, message: '请选择二级分类', trigger: 'change' }],
  name: [
    { required: true, message: '请输入商品名称', trigger: 'blur' },
    { min: 2, max: 120, message: '商品名称需 2–120 个字符', trigger: 'blur' },
  ],
}

const leafCategories = computed(() => categories.value.filter((item) => item.level === 2))

const skuDialogVisible = ref(false)
const skuSaving = ref(false)
const editingSkuId = ref<string | null>(null)
const skuFormRef = ref<FormInstance>()
const skuForm = reactive({
  sku_code: '',
  spec_text: '',
  sale_price: '',
  original_price: '',
  stock: 0,
  stock_capacity: 100,
  weight_grams: 0,
  status: 'ON_SALE' as SkuStatus,
})
const skuRules: FormRules = {
  sku_code: [
    { required: true, message: '请输入 SKU 编码', trigger: 'blur' },
    {
      pattern: /^[A-Za-z0-9-]{8,32}$/,
      message: '需 8–32 位字母、数字或连字符',
      trigger: 'blur',
    },
  ],
  spec_text: [{ required: true, message: '请输入规格描述', trigger: 'blur' }],
  sale_price: [{ required: true, message: '请输入售价', trigger: 'blur' }],
}

const stockDialogVisible = ref(false)
const stockSaving = ref(false)
const stockTarget = ref<AdminSku | null>(null)
const stockForm = reactive({ change: 1, reason: '' })

const pageTitle = computed(() => (isNew.value ? '新建商品' : product.value?.name || '编辑商品'))

async function loadProduct() {
  if (isNew.value) {
    product.value = null
    skus.value = []
    Object.assign(form, {
      category_public_id: '',
      name: '',
      subtitle: '',
      description: '',
      sort_weight: 0,
    })
    return
  }
  loading.value = true
  try {
    const [detail, skuList] = await Promise.all([
      fetchAdminProduct(productId.value),
      fetchAdminSkus(productId.value),
    ])
    product.value = detail
    skus.value = skuList
    Object.assign(form, {
      category_public_id: detail.category.public_id,
      name: detail.name,
      subtitle: detail.subtitle,
      description: detail.description,
      sort_weight: detail.sort_weight,
    })
  } finally {
    loading.value = false
  }
}

async function saveProduct() {
  if (!formRef.value) {
    return
  }
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) {
    return
  }
  saving.value = true
  try {
    if (isNew.value) {
      const created = await createProduct({ ...form })
      ElMessage.success('商品已创建，请补充 SKU 后上架')
      await router.replace({ name: 'admin-product-edit', params: { publicId: created.public_id } })
      await loadProduct()
    } else {
      await updateProduct(productId.value, { ...form })
      ElMessage.success('商品已保存')
      await loadProduct()
    }
  } finally {
    saving.value = false
  }
}

async function handleUpload(options: UploadRequestOptions) {
  if (!productId.value) {
    return
  }
  uploading.value = true
  try {
    await uploadProductImage(productId.value, options.file)
    ElMessage.success('图片已上传')
    await loadProduct()
  } finally {
    uploading.value = false
  }
}

async function removeImage(imagePublicId: string) {
  const confirmed = await ElMessageBox.confirm('确定删除这张商品图吗？', '删除图片', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消',
  }).catch(() => false)
  if (!confirmed) {
    return
  }
  await deleteProductImage(productId.value, imagePublicId)
  ElMessage.success('图片已删除')
  await loadProduct()
}

function openSkuCreate() {
  editingSkuId.value = null
  Object.assign(skuForm, {
    sku_code: '',
    spec_text: '',
    sale_price: '',
    original_price: '',
    stock: 0,
    stock_capacity: 100,
    weight_grams: 0,
    status: 'ON_SALE',
  })
  skuDialogVisible.value = true
  nextTick(() => skuFormRef.value?.clearValidate())
}

function openSkuEdit(sku: AdminSku) {
  editingSkuId.value = sku.public_id
  Object.assign(skuForm, {
    sku_code: sku.sku_code,
    spec_text: sku.spec_text,
    sale_price: sku.sale_price,
    original_price: sku.original_price ?? '',
    stock: sku.stock,
    stock_capacity: sku.stock_capacity,
    weight_grams: sku.weight_grams,
    status: sku.status,
  })
  skuDialogVisible.value = true
  nextTick(() => skuFormRef.value?.clearValidate())
}

async function saveSku() {
  if (!skuFormRef.value) {
    return
  }
  const valid = await skuFormRef.value.validate().catch(() => false)
  if (!valid) {
    return
  }
  const payload: AdminSkuPayload = {
    sku_code: skuForm.sku_code,
    spec_text: skuForm.spec_text,
    sale_price: skuForm.sale_price,
    original_price: skuForm.original_price || null,
    stock: skuForm.stock,
    stock_capacity: skuForm.stock_capacity,
    weight_grams: skuForm.weight_grams,
    status: skuForm.status,
  }
  skuSaving.value = true
  try {
    if (editingSkuId.value) {
      await updateSku(editingSkuId.value, payload)
      ElMessage.success('SKU 已更新')
    } else {
      await createSku(productId.value, payload)
      ElMessage.success('SKU 已创建')
    }
    skuDialogVisible.value = false
    await loadProduct()
  } finally {
    skuSaving.value = false
  }
}

function openStockAdjust(sku: AdminSku) {
  stockTarget.value = sku
  Object.assign(stockForm, { change: 1, reason: '' })
  stockDialogVisible.value = true
}

async function submitStockAdjust() {
  if (!stockTarget.value || stockForm.change <= 0) {
    return
  }
  stockSaving.value = true
  try {
    await adjustStock(stockTarget.value.public_id, stockForm.change, stockForm.reason)
    ElMessage.success('库存已调整并写入流水')
    stockDialogVisible.value = false
    await loadProduct()
  } finally {
    stockSaving.value = false
  }
}

async function toggleSale() {
  if (!product.value) {
    return
  }
  if (product.value.status === 'ON_SALE') {
    await unpublishProduct(productId.value)
    ElMessage.success('商品已下架')
  } else {
    await publishProduct(productId.value)
    ElMessage.success('商品已上架')
  }
  await loadProduct()
}

onMounted(async () => {
  categories.value = await fetchAdminCategories()
  await loadProduct()
})
</script>

<template>
  <section v-loading="loading" class="admin-edit">
    <header class="admin-edit__header">
      <div>
        <p class="admin-edit__eyebrow">
          <el-button link @click="router.push({ name: 'admin-products' })">商品管理</el-button>
          / {{ isNew ? '新建商品' : '编辑商品' }}
        </p>
        <h1>
          {{ pageTitle }}
          <el-tag
            v-if="product"
            :type="productStatusTone(product.status as ProductStatus)"
            size="small"
          >
            {{ productStatusLabel(product.status as ProductStatus) }}
          </el-tag>
        </h1>
      </div>
      <div class="admin-edit__actions">
        <el-button v-if="product" @click="toggleSale">
          {{ product.status === 'ON_SALE' ? '下架' : '上架' }}
        </el-button>
        <el-button type="primary" :loading="saving" @click="saveProduct">保存商品</el-button>
      </div>
    </header>

    <el-alert
      v-if="isNew && leafCategories.length === 0"
      type="warning"
      :closable="false"
      title="还没有二级分类，请先到分类管理创建一级 + 二级分类。"
      class="admin-edit__alert"
    />

    <div class="admin-edit__grid">
      <div class="admin-edit__card">
        <h2>基础信息</h2>
        <el-form ref="formRef" :model="form" :rules="rules" label-width="96px">
          <el-form-item label="所属分类" prop="category_public_id">
            <el-select v-model="form.category_public_id" placeholder="选择二级分类" filterable>
              <el-option
                v-for="category in leafCategories"
                :key="category.public_id"
                :label="category.name"
                :value="category.public_id"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="商品名称" prop="name">
            <el-input v-model="form.name" maxlength="120" show-word-limit />
          </el-form-item>
          <el-form-item label="副标题">
            <el-input v-model="form.subtitle" maxlength="200" show-word-limit />
          </el-form-item>
          <el-form-item label="排序权重">
            <el-input-number v-model="form.sort_weight" :min="0" :max="9999" />
          </el-form-item>
          <el-form-item label="商品详情">
            <el-input v-model="form.description" type="textarea" :rows="6" />
          </el-form-item>
        </el-form>
      </div>

      <div class="admin-edit__side">
        <div class="admin-edit__card">
          <h2>商品图集</h2>
          <p v-if="isNew" class="admin-edit__muted">保存商品后可上传图片。</p>
          <template v-else>
            <div class="admin-edit__images">
              <div v-for="image in product?.images ?? []" :key="image.public_id" class="image-item">
                <img :src="resolveImageUrl(image.image)" alt="商品图" />
                <el-button link type="danger" size="small" @click="removeImage(image.public_id)">
                  删除
                </el-button>
              </div>
              <el-upload
                :show-file-list="false"
                :http-request="handleUpload"
                accept="image/jpeg,image/png,image/webp"
              >
                <el-button :loading="uploading">上传图片</el-button>
              </el-upload>
            </div>
            <p class="admin-edit__muted">
              支持 jpg / png / webp，单张 ≤ 5MB，尺寸 ≤ 4096px；首图自动作为主图。
            </p>
          </template>
        </div>

        <div v-if="product" class="admin-edit__card">
          <h2>销售概览</h2>
          <dl class="admin-edit__stats">
            <div>
              <dt>价格区间</dt>
              <dd>{{ formatPriceRange(product.price_min, product.price_max) }}</dd>
            </div>
            <div>
              <dt>SKU 数</dt>
              <dd>{{ product.sku_count }}</dd>
            </div>
            <div>
              <dt>可售库存</dt>
              <dd>{{ product.stock_total }}</dd>
            </div>
            <div>
              <dt>销量</dt>
              <dd>{{ product.sales_count }}</dd>
            </div>
          </dl>
        </div>
      </div>
    </div>

    <div v-if="product" class="admin-edit__card">
      <div class="admin-edit__card-head">
        <h2>SKU 与库存</h2>
        <el-button type="primary" @click="openSkuCreate">新建 SKU</el-button>
      </div>

      <el-table :data="skus" border stripe>
        <el-table-column prop="sku_code" label="SKU 编码" width="160" />
        <el-table-column prop="spec_text" label="规格" min-width="140" />
        <el-table-column label="售价" width="120">
          <template #default="{ row }">{{ formatCurrency(row.sale_price) }}</template>
        </el-table-column>
        <el-table-column label="划线价" width="120">
          <template #default="{ row }">
            {{ row.original_price ? formatCurrency(row.original_price) : '—' }}
          </template>
        </el-table-column>
        <el-table-column label="库存" width="140">
          <template #default="{ row }">
            <span>{{ row.stock }}</span>
            <span class="admin-edit__muted"> / 上限 {{ row.stock_capacity }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'ON_SALE' ? 'success' : 'info'" size="small">
              {{ row.status === 'ON_SALE' ? '在售' : '已下架' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openSkuEdit(row)">编辑</el-button>
            <el-button link type="primary" @click="openStockAdjust(row)">调整库存</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog
      v-model="skuDialogVisible"
      :title="editingSkuId ? '编辑 SKU' : '新建 SKU'"
      width="520px"
    >
      <el-form ref="skuFormRef" :model="skuForm" :rules="skuRules" label-width="96px">
        <el-form-item label="SKU 编码" prop="sku_code">
          <el-input v-model="skuForm.sku_code" placeholder="如 DRESS-001" />
        </el-form-item>
        <el-form-item label="规格描述" prop="spec_text">
          <el-input v-model="skuForm.spec_text" placeholder="如 米白 / M" />
        </el-form-item>
        <el-form-item label="售价" prop="sale_price">
          <el-input v-model="skuForm.sale_price" placeholder="99.00" />
        </el-form-item>
        <el-form-item label="划线价">
          <el-input v-model="skuForm.original_price" placeholder="可留空" />
        </el-form-item>
        <el-form-item label="可售库存">
          <el-input-number v-model="skuForm.stock" :min="0" />
        </el-form-item>
        <el-form-item label="库存上限">
          <el-input-number v-model="skuForm.stock_capacity" :min="0" />
        </el-form-item>
        <el-form-item label="重量(克)">
          <el-input-number v-model="skuForm.weight_grams" :min="0" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="skuForm.status">
            <el-option label="在售" value="ON_SALE" />
            <el-option label="已下架" value="OFF_SALE" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="skuDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="skuSaving" @click="saveSku">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="stockDialogVisible" title="调整库存（仅增量）" width="420px">
      <p class="admin-edit__muted">
        {{ stockTarget?.sku_code }} · {{ stockTarget?.spec_text }} 当前库存
        {{ stockTarget?.stock }}，上限 {{ stockTarget?.stock_capacity }}
      </p>
      <el-form label-width="80px">
        <el-form-item label="增加数量">
          <el-input-number v-model="stockForm.change" :min="1" />
        </el-form-item>
        <el-form-item label="调整原因">
          <el-input v-model="stockForm.reason" maxlength="100" placeholder="如 供应商补货" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="stockDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="stockSaving" @click="submitStockAdjust">
          确认调整
        </el-button>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped lang="scss">
.admin-edit {
  &__header {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 20px;

    h1 {
      font-size: 26px;
      display: flex;
      align-items: center;
      gap: 10px;
    }
  }

  &__eyebrow {
    color: var(--guda-text-muted);
    font-size: 12px;
    margin-bottom: 6px;
  }

  &__actions {
    display: flex;
    gap: 8px;
  }

  &__alert {
    margin-bottom: 16px;
  }

  &__grid {
    display: grid;
    grid-template-columns: minmax(0, 1.4fr) minmax(300px, 0.6fr);
    gap: 20px;
    margin-bottom: 20px;
  }

  &__side {
    display: flex;
    flex-direction: column;
    gap: 20px;
  }

  &__card {
    border: 1px solid var(--guda-border);
    border-radius: var(--guda-radius);
    background: var(--guda-surface);
    padding: 20px 24px;

    h2 {
      font-size: 17px;
      margin-bottom: 16px;
    }
  }

  &__card-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;

    h2 {
      margin-bottom: 0;
    }
  }

  &__muted {
    color: var(--guda-text-muted);
    font-size: 12px;
  }

  &__images {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    align-items: center;
  }

  &__stats {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 14px;
    margin: 0;

    dt {
      color: var(--guda-text-muted);
      font-size: 12px;
      margin-bottom: 4px;
    }

    dd {
      margin: 0;
      font-weight: 600;
    }
  }

  &__pagination {
    margin-top: 18px;
  }
}

.image-item {
  width: 92px;
  text-align: center;

  img {
    width: 92px;
    height: 92px;
    object-fit: cover;
    border-radius: 8px;
    border: 1px solid var(--guda-border);
    margin-bottom: 4px;
  }
}

@media (max-width: 991px) {
  .admin-edit__grid {
    grid-template-columns: 1fr;
  }
}
</style>
