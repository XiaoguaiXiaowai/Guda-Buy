<script setup lang="ts">
import type { FormInstance, FormRules } from 'element-plus'
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const formRef = ref<FormInstance>()
const submitting = ref(false)
const form = reactive({
  account: '',
  password: '',
})

const rules: FormRules = {
  account: [{ required: true, message: '请输入用户名或邮箱', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function submit() {
  if (!formRef.value) {
    return
  }
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) {
    return
  }
  submitting.value = true
  try {
    await auth.login({ account: form.account.trim(), password: form.password })
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/user/profile'
    await router.replace(redirect)
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
        <h1 class="auth-card__title">欢迎回来</h1>
        <p class="auth-card__desc">登录后可管理个人资料与收货地址。</p>
      </header>

      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent>
        <el-form-item label="用户名 / 邮箱" prop="account">
          <el-input
            v-model="form.account"
            size="large"
            placeholder="请输入用户名或邮箱"
            autocomplete="username"
            @keyup.enter="submit"
          />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            size="large"
            type="password"
            show-password
            placeholder="请输入密码"
            autocomplete="current-password"
            @keyup.enter="submit"
          />
        </el-form-item>

        <div class="auth-card__aux">
          <RouterLink class="auth-link" to="/forgot-password">忘记密码？</RouterLink>
        </div>

        <el-button
          class="auth-card__submit"
          type="primary"
          size="large"
          :loading="submitting"
          @click="submit"
        >
          登录
        </el-button>
      </el-form>

      <p class="auth-card__footer">
        还没有账号？
        <RouterLink class="auth-link" to="/register">立即注册</RouterLink>
      </p>
    </div>
  </section>
</template>
