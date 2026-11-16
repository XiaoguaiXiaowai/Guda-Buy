<script setup lang="ts">
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, nextTick, onMounted, reactive, ref } from 'vue'

import { createCategory, deleteCategory, fetchAdminCategories, updateCategory } from '@/api/catalog'
import type { AdminCategory } from '@/types/catalog'

const categories = ref<AdminCategory[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const saving = ref(false)
const editingId = ref<string | null>(null)
const formRef = ref<FormInstance>()

const form = reactive({
  name: '',
  parent_public_id: '',
  sort_weight: 0,
})

const rules: FormRules = {
  name: [
    { required: true, message: '请输入分类名称', trigger: 'blur' },
    { min: 1, max: 60, message: '分类名称需 1–60 个字符', trigger: 'blur' },
  ],
}

const parentOptions = computed(() => categories.value.filter((item) => item.level === 1))
const categoryNames = computed(
  () => new Map(categories.value.map((item) => [item.public_id, item.name])),
)
const dialogTitle = computed(() => (editingId.value ? '编辑分类' : '新建分类'))

async function load() {
  loading.value = true
  try {
    categories.value = await fetchAdminCategories()
  } finally {
    loading.value = false
  }
}

async function openCreate() {
  editingId.value = null
  Object.assign(form, { name: '', parent_public_id: '', sort_weight: 0 })
  dialogVisible.value = true
  await nextTick()
  formRef.value?.clearValidate()
}

async function openEdit(category: AdminCategory) {
  editingId.value = category.public_id
  Object.assign(form, {
    name: category.name,
    parent_public_id: category.parent_public_id ?? '',
    sort_weight: category.sort_weight,
  })
  dialogVisible.value = true
  await nextTick()
  formRef.value?.clearValidate()
}

async function save() {
  if (!formRef.value) {
    return
  }
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) {
    return
  }
  saving.value = true
  try {
    if (editingId.value) {
      await updateCategory(editingId.value, {
        name: form.name,
        sort_weight: form.sort_weight,
      })
      ElMessage.success('分类已更新')
    } else {
      await createCategory({
        name: form.name,
        parent_public_id: form.parent_public_id || undefined,
        sort_weight: form.sort_weight,
      })
      ElMessage.success('分类已创建')
    }
    dialogVisible.value = false
    await load()
  } finally {
    saving.value = false
  }
}

async function remove(category: AdminCategory) {
  const confirmed = await ElMessageBox.confirm(
    `确定删除分类「${category.name}」吗？存在商品或子分类时不可删除。`,
    '删除分类',
    { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
  ).catch(() => false)
  if (!confirmed) {
    return
  }
  await deleteCategory(category.public_id)
  ElMessage.success('分类已删除')
  await load()
}

onMounted(load)
</script>

<template>
  <section class="admin-page">
    <header class="admin-page__header">
      <div>
        <p class="admin-page__eyebrow">商品后台</p>
        <h1>分类管理</h1>
      </div>
      <el-button type="primary" @click="openCreate">新建分类</el-button>
    </header>

    <el-table v-loading="loading" :data="categories" border stripe>
      <el-table-column prop="name" label="分类名称" min-width="180" />
      <el-table-column label="层级" width="100">
        <template #default="{ row }">
          <el-tag :type="row.level === 1 ? 'primary' : 'info'" effect="plain" size="small">
            {{ row.level === 1 ? '一级' : '二级' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="上级分类" min-width="140">
        <template #default="{ row }">
          {{ row.parent_public_id ? categoryNames.get(row.parent_public_id) : '—' }}
        </template>
      </el-table-column>
      <el-table-column prop="product_count" label="商品数" width="100" />
      <el-table-column prop="sort_weight" label="排序" width="90" />
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="460px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="分类名称" prop="name">
          <el-input v-model="form.name" maxlength="60" show-word-limit />
        </el-form-item>
        <el-form-item label="上级分类">
          <el-select
            v-model="form.parent_public_id"
            placeholder="不选则创建一级分类"
            clearable
            :disabled="Boolean(editingId)"
          >
            <el-option
              v-for="parent in parentOptions"
              :key="parent.public_id"
              :label="parent.name"
              :value="parent.public_id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="排序权重">
          <el-input-number v-model="form.sort_weight" :min="0" :max="9999" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
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
}
</style>
