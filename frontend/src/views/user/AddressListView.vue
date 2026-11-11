<script setup lang="ts">
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import { nextTick, onMounted, reactive, ref } from 'vue'

import {
  createAddress,
  deleteAddress,
  listAddresses,
  setDefaultAddress,
  updateAddress,
} from '@/api/user'
import type { Address, AddressPayload } from '@/types/user'

const addresses = ref<Address[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const saving = ref(false)
const editingId = ref<string | null>(null)
const formRef = ref<FormInstance>()

const emptyForm = (): AddressPayload => ({
  receiver_name: '',
  phone: '',
  province: '',
  city: '',
  district: '',
  detail: '',
  postal_code: '',
  is_default: false,
})

const form = reactive<AddressPayload>(emptyForm())

const rules: FormRules = {
  receiver_name: [
    { required: true, message: '请输入收货人', trigger: 'blur' },
    { min: 2, max: 20, message: '收货人需 2–20 位', trigger: 'blur' },
  ],
  phone: [
    { required: true, message: '请输入手机号', trigger: 'blur' },
    { pattern: /^1[3-9]\d{9}$/, message: '请输入正确的中国大陆手机号', trigger: 'blur' },
  ],
  province: [{ required: true, message: '请输入省份', trigger: 'blur' }],
  city: [{ required: true, message: '请输入城市', trigger: 'blur' }],
  district: [{ required: true, message: '请输入区/县', trigger: 'blur' }],
  detail: [{ required: true, message: '请输入详细地址', trigger: 'blur' }],
  postal_code: [{ pattern: /^\d{6}$/, message: '邮编需为 6 位数字', trigger: 'blur' }],
}

async function load() {
  loading.value = true
  try {
    addresses.value = await listAddresses()
  } finally {
    loading.value = false
  }
}

async function openCreate() {
  editingId.value = null
  Object.assign(form, emptyForm())
  dialogVisible.value = true
  await nextTick()
  formRef.value?.clearValidate()
}

async function openEdit(address: Address) {
  editingId.value = address.public_id
  Object.assign(form, {
    receiver_name: address.receiver_name,
    phone: address.phone,
    province: address.province,
    city: address.city,
    district: address.district,
    detail: address.detail,
    postal_code: address.postal_code,
    is_default: address.is_default,
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
    const payload: AddressPayload = { ...form }
    if (editingId.value) {
      await updateAddress(editingId.value, payload)
      ElMessage.success('地址已更新')
    } else {
      await createAddress(payload)
      ElMessage.success('地址已添加')
    }
    dialogVisible.value = false
    await load()
  } finally {
    saving.value = false
  }
}

async function remove(address: Address) {
  const confirmed = await ElMessageBox.confirm(
    `确定删除「${address.receiver_name}」的收货地址吗？`,
    '删除地址',
    { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
  ).catch(() => false)
  if (!confirmed) {
    return
  }
  await deleteAddress(address.public_id)
  ElMessage.success('地址已删除')
  await load()
}

async function markDefault(address: Address) {
  if (address.is_default) {
    return
  }
  await setDefaultAddress(address.public_id)
  ElMessage.success('已设为默认地址')
  await load()
}

onMounted(load)
</script>

<template>
  <section class="user-page">
    <header class="user-page__header">
      <div>
        <h1 class="user-page__title">收货地址</h1>
        <p class="user-page__desc">最多可保存 20 条地址，下单时默认使用默认地址。</p>
      </div>
      <nav class="user-tabs" aria-label="个人中心导航">
        <RouterLink to="/user/profile">个人资料</RouterLink>
        <RouterLink to="/user/addresses">收货地址</RouterLink>
      </nav>
    </header>

    <div v-loading="loading" class="address-panel">
      <div class="address-panel__toolbar">
        <span class="address-panel__count">已保存 {{ addresses.length }} / 20 条</span>
        <el-button type="primary" @click="openCreate">新增地址</el-button>
      </div>

      <el-empty v-if="!loading && addresses.length === 0" description="还没有收货地址">
        <el-button type="primary" @click="openCreate">添加第一条地址</el-button>
      </el-empty>

      <div v-else class="address-grid">
        <article
          v-for="address in addresses"
          :key="address.public_id"
          class="address-card"
          :class="{ 'address-card--default': address.is_default }"
        >
          <header class="address-card__header">
            <div class="address-card__name">
              <span>{{ address.receiver_name }}</span>
              <span class="address-card__phone">{{ address.phone }}</span>
            </div>
            <el-tag v-if="address.is_default" type="primary" effect="light" size="small">
              默认
            </el-tag>
          </header>

          <p class="address-card__region">
            {{ address.province }} {{ address.city }} {{ address.district }}
          </p>
          <p class="address-card__detail">{{ address.detail }}</p>
          <p v-if="address.postal_code" class="address-card__postal">
            邮编 {{ address.postal_code }}
          </p>

          <footer class="address-card__actions">
            <el-button link type="primary" @click="openEdit(address)">编辑</el-button>
            <el-button
              v-if="!address.is_default"
              link
              type="primary"
              @click="markDefault(address)"
            >
              设为默认
            </el-button>
            <el-button link type="danger" @click="remove(address)">删除</el-button>
          </footer>
        </article>
      </div>
    </div>

    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑地址' : '新增地址'"
      width="560px"
      destroy-on-close
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="88px">
        <el-form-item label="收货人" prop="receiver_name">
          <el-input v-model="form.receiver_name" maxlength="20" placeholder="2–20 位中文或字母" />
        </el-form-item>
        <el-form-item label="手机号" prop="phone">
          <el-input v-model="form.phone" maxlength="11" placeholder="11 位手机号" />
        </el-form-item>
        <el-form-item label="省份" prop="province">
          <el-input v-model="form.province" maxlength="64" placeholder="如：广东省" />
        </el-form-item>
        <el-form-item label="城市" prop="city">
          <el-input v-model="form.city" maxlength="64" placeholder="如：深圳市" />
        </el-form-item>
        <el-form-item label="区/县" prop="district">
          <el-input v-model="form.district" maxlength="64" placeholder="如：南山区" />
        </el-form-item>
        <el-form-item label="详细地址" prop="detail">
          <el-input
            v-model="form.detail"
            type="textarea"
            :rows="2"
            maxlength="200"
            show-word-limit
            placeholder="街道、门牌号等"
          />
        </el-form-item>
        <el-form-item label="邮编" prop="postal_code">
          <el-input v-model="form.postal_code" maxlength="6" placeholder="选填，6 位数字" />
        </el-form-item>
        <el-form-item label="默认地址">
          <el-switch v-model="form.is_default" />
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
.user-page {
  &__header {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 24px;
  }

  &__title {
    font-size: 26px;
    margin-bottom: 6px;
  }

  &__desc {
    color: var(--guda-text-muted);
    font-size: 14px;
  }
}

.user-tabs {
  display: flex;
  gap: 20px;
  font-size: 14px;

  a {
    color: var(--guda-text-muted);
    text-decoration: none;
    padding-bottom: 4px;
    border-bottom: 2px solid transparent;

    &.router-link-active {
      color: var(--guda-primary);
      border-color: var(--guda-primary);
    }
  }
}

.address-panel {
  min-height: 240px;

  &__toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 20px;
  }

  &__count {
    font-size: 13px;
    color: var(--guda-text-muted);
  }
}

.address-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.address-card {
  background: var(--guda-surface);
  border: 1px solid var(--guda-border);
  border-radius: var(--guda-radius);
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 6px;

  &--default {
    border-color: var(--guda-primary);
    box-shadow: 0 0 0 1px var(--guda-primary-soft) inset;
  }

  &__header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 6px;
  }

  &__name {
    font-weight: 600;
    display: flex;
    align-items: baseline;
    gap: 10px;
    flex-wrap: wrap;
  }

  &__phone {
    font-weight: 400;
    font-size: 13px;
    color: var(--guda-text-muted);
  }

  &__region {
    font-size: 13px;
    color: var(--guda-text-muted);
  }

  &__detail {
    font-size: 14px;
    line-height: 1.6;
  }

  &__postal {
    font-size: 12px;
    color: var(--guda-text-muted);
  }

  &__actions {
    margin-top: auto;
    padding-top: 12px;
    border-top: 1px solid var(--guda-border);
    display: flex;
    gap: 4px;
  }
}

@media (max-width: 991px) {
  .address-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 767px) {
  .user-page__header {
    flex-direction: column;
    align-items: flex-start;
  }

  .address-grid {
    grid-template-columns: 1fr;
  }
}
</style>
