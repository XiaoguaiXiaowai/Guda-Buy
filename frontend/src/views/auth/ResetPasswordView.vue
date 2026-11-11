<script setup lang="ts">
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage } from 'element-plus'
import { computed, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { confirmPasswordReset } from '@/api/user'

const route = useRoute()
const router = useRouter()

const token = computed(() => (typeof route.query.token === 'string' ? route.query.token : ''))
const formRef = ref<FormInstance>()
const submitting = ref(false)
const form = reactive({
  password: '',
  confirmPassword: '',
})

const rules: FormRules = {
  password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 8, max: 64, message: '密码长度需为 8–64 位', trigger: 'blur' },
    {
      pattern: /^(?=.*[A-Za-z])(?=.*\d).+$/,
      message: '密码需同时包含字母与数字',
      trigger: 'blur',
    },
  ],
  confirmPassword: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    {
      validator: (_rule, value, callback) => {
        if (value !== form.password) {
          callback(new Error('两次输入的密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur',
    },
  ],
}

async function submit() {
  if (!token.value) {
    ElMessage.error('重置链接无效，请重新申请')
    return
  }
  if (!formRef.value) {
    return
  }
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) {
    return
  }
  submitting.value = true
  try {
    await confirmPasswordReset(token.value, form.password)
    ElMessage.success('密码已重置，请使用新密码登录')
    await router.replace('/login')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <section class="auth-page">
    <div class="auth-card">
      <header class="auth-card__header">
        <p class="auth-card__eyebrow">GUDA 商城</p>
        <h1 class="auth-card__title">设置新密码</h1>
        <p class="auth-card__desc">重置成功后，其他设备上的登录状态将全部失效。</p>
      </header>

      <el-alert
        v-if="!token"
        type="error"
        :closable="false"
        title="重置链接无效"
        description="缺少重置凭证，请回到找回密码页面重新申请。"
        class="auth-card__alert"
      />

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        @submit.prevent
      >
        <el-form-item label="新密码" prop="password">
          <el-input
            v-model="form.password"
            size="large"
            type="password"
            show-password
            placeholder="8–64 位，需包含字母与数字"
            autocomplete="new-password"
          />
        </el-form-item>
        <el-form-item label="确认新密码" prop="confirmPassword">
          <el-input
            v-model="form.confirmPassword"
            size="large"
            type="password"
            show-password
            placeholder="请再次输入新密码"
            autocomplete="new-password"
            @keyup.enter="submit"
          />
        </el-form-item>

        <el-button
          class="auth-card__submit"
          type="primary"
          size="large"
          :loading="submitting"
          :disabled="!token"
          @click="submit"
        >
          确认重置
        </el-button>
      </el-form>

      <p class="auth-card__footer">
        <RouterLink class="auth-link" to="/forgot-password">重新申请重置</RouterLink>
      </p>
    </div>
  </section>
</template>
