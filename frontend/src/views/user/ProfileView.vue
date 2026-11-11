<script setup lang="ts">
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage } from 'element-plus'
import { reactive, ref, watch } from 'vue'

import { updateMe, uploadAvatar } from '@/api/user'
import { useAuthStore } from '@/stores/auth'
import type { Gender } from '@/types/user'
import { formatDateTime } from '@/utils/format'

const auth = useAuthStore()
const formRef = ref<FormInstance>()
const fileInputRef = ref<HTMLInputElement>()
const saving = ref(false)
const uploading = ref(false)

const form = reactive({
  nickname: '',
  gender: 'UNKNOWN' as Gender,
  birthday: '',
})

const rules: FormRules = {
  nickname: [
    { required: true, message: '请输入昵称', trigger: 'blur' },
    {
      pattern: /^[\w\u4e00-\u9fa5]{1,30}$/,
      message: '昵称仅支持中文、字母、数字、下划线',
      trigger: 'blur',
    },
  ],
}

watch(
  () => auth.user,
  (profile) => {
    if (!profile) {
      return
    }
    form.nickname = profile.nickname
    form.gender = profile.gender
    form.birthday = profile.birthday ?? ''
  },
  { immediate: true },
)

async function saveProfile() {
  if (!formRef.value) {
    return
  }
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) {
    return
  }
  saving.value = true
  try {
    const profile = await updateMe({
      nickname: form.nickname.trim(),
      gender: form.gender,
      birthday: form.birthday || null,
    })
    auth.setProfile(profile)
    ElMessage.success('个人资料已更新')
  } finally {
    saving.value = false
  }
}

function pickAvatar() {
  fileInputRef.value?.click()
}

async function onFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) {
    return
  }
  if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
    ElMessage.error('仅支持 jpg/jpeg/png/webp 格式图片')
    return
  }
  if (file.size > 5 * 1024 * 1024) {
    ElMessage.error('头像文件不能超过 5MB')
    return
  }
  uploading.value = true
  try {
    const profile = await uploadAvatar(file)
    auth.setProfile(profile)
    ElMessage.success('头像已更新')
  } finally {
    uploading.value = false
  }
}
</script>

<template>
  <section class="user-page">
    <header class="user-page__header">
      <div>
        <h1 class="user-page__title">个人中心</h1>
        <p class="user-page__desc">管理你的昵称、头像与收货地址。</p>
      </div>
      <nav class="user-tabs" aria-label="个人中心导航">
        <RouterLink to="/user/profile">个人资料</RouterLink>
        <RouterLink to="/user/addresses">收货地址</RouterLink>
      </nav>
    </header>

    <div class="profile-card">
      <aside class="profile-card__side">
        <el-avatar :size="96" :src="auth.user?.avatar ?? undefined" class="profile-card__avatar">
          {{ auth.user?.nickname?.slice(0, 1) ?? 'G' }}
        </el-avatar>
        <el-button size="small" :loading="uploading" @click="pickAvatar">更换头像</el-button>
        <input
          ref="fileInputRef"
          class="profile-card__file"
          type="file"
          accept="image/jpeg,image/png,image/webp"
          @change="onFileChange"
        />
        <p class="profile-card__hint">支持 jpg/png/webp，最大 5MB</p>

        <dl class="profile-meta">
          <div>
            <dt>用户名</dt>
            <dd>{{ auth.user?.username }}</dd>
          </div>
          <div>
            <dt>邮箱</dt>
            <dd>{{ auth.user?.email }}</dd>
          </div>
          <div>
            <dt>注册时间</dt>
            <dd>{{ formatDateTime(auth.user?.created_at) }}</dd>
          </div>
        </dl>
      </aside>

      <div class="profile-card__main">
        <h2 class="profile-card__title">基础资料</h2>
        <el-form ref="formRef" :model="form" :rules="rules" label-width="88px">
          <el-form-item label="昵称" prop="nickname">
            <el-input v-model="form.nickname" maxlength="30" show-word-limit />
          </el-form-item>
          <el-form-item label="性别" prop="gender">
            <el-radio-group v-model="form.gender">
              <el-radio value="UNKNOWN">保密</el-radio>
              <el-radio value="MALE">男</el-radio>
              <el-radio value="FEMALE">女</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="生日" prop="birthday">
            <el-date-picker
              v-model="form.birthday"
              type="date"
              value-format="YYYY-MM-DD"
              placeholder="选择生日"
              :disabled-date="(date: Date) => date.getTime() > Date.now()"
            />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="saving" @click="saveProfile">保存修改</el-button>
          </el-form-item>
        </el-form>
      </div>
    </div>
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

.profile-card {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  gap: 32px;
  background: var(--guda-surface);
  border: 1px solid var(--guda-border);
  border-radius: var(--guda-radius);
  padding: 32px;

  &__side {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
    padding-right: 32px;
    border-right: 1px solid var(--guda-border);
  }

  &__avatar {
    background: var(--guda-primary-soft);
    color: var(--guda-primary);
    font-size: 32px;
  }

  &__file {
    display: none;
  }

  &__hint {
    font-size: 12px;
    color: var(--guda-text-muted);
  }

  &__title {
    font-size: 16px;
    margin-bottom: 20px;
  }
}

.profile-meta {
  width: 100%;
  margin: 12px 0 0;
  font-size: 13px;

  div {
    margin-bottom: 14px;
  }

  dt {
    color: var(--guda-text-muted);
    margin-bottom: 4px;
  }

  dd {
    margin: 0;
    word-break: break-all;
  }
}

@media (max-width: 767px) {
  .user-page__header {
    flex-direction: column;
    align-items: flex-start;
  }

  .profile-card {
    grid-template-columns: 1fr;
    padding: 22px;

    &__side {
      border-right: none;
      border-bottom: 1px solid var(--guda-border);
      padding: 0 0 20px;
    }
  }
}
</style>
